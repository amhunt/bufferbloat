from mininet.topo import Topo
from time import sleep
from mininet.node import CPULimitedHost, OVSController
from mininet.link import TCLink
from mininet.net import Mininet
from mininet.log import lg, info
from mininet.util import dumpNodeConnections
from time import time
from multiprocessing import Process
import os
from subprocess import call, Popen
from monitor import monitor_qlen
import numpy
import sys

import matplotlib
import numpy as np
import matplotlib.pyplot as plt

import windowgraph

class BBTopo(Topo):
    "Simple topology for bufferbloat experiment."
# FIX: why does it say the below?
# Note that you may need to change the constructor to pass special parameters to the topology
    def __init__(self, queue_size, ping_RTT):

        super(BBTopo, self).__init__()
        # Here we have created a switch.  If you change its name, its
        # interface names will change from s0-eth1 to newname-eth1.
        s0 = self.addSwitch('s0')
        
        # Create two hosts
        h1 = self.addHost('h1')
        h2 = self.addHost('h2')
        
        # Add links with appropriate characteristics
        self.addLink( h1, s0, bw=1000, delay='%dms' % ping_RTT, max_queue_size=queue_size )
        self.addLink( h2, s0, bw=1.5, delay='%dms' % ping_RTT, max_queue_size=queue_size )
        
        return

def start_iperf(net, congestion_window):
    h1 = net.getNodeByName('h1')
    h2 = net.getNodeByName('h2')

    print "Starting iperf server..."
    # For those who are curious about the -w 16m parameter, it ensures
    # that the TCP flow is not receiver window limited.  If it is,
    # there is a chance that the router buffer may not get filled up.
    server = h2.popen("iperf -s -w %s" % congestion_window)
    
    # TODO: Start the iperf client on h1.  Ensure that you create a
    # long lived TCP flow.
    client = h1.popen("iperf -c %s -t %d" % (h2.IP(),  400))

def start_ping(net):
    h1 = net.getNodeByName('h1')
    h2 = net.getNodeByName('h2')
    # TODO: Start a ping train from h1 to h2 (or h2 to h1, does it
    # matter?)  Measure RTTs every 0.1 second.  Read the ping man page
    # to see how to do this.

    # Hint: Use host.popen(cmd, shell=True).  If you pass shell=True
    # to popen, you can redirect cmd's output using shell syntax.
    # i.e. ping ... > /path/to/ping.
    cmd = "ping -i 0.1 %s > %s/pingoutput.txt" % (h2.IP(), ".")

    ping = h1.popen(cmd, shell=True)

def start_tcpprobe(outfile="cwnd.txt"):
    os.system("rmmod tcp_probe; modprobe tcp_probe full=1;")
    Popen("cat /proc/net/tcpprobe > %s" % outfile, shell=True)

def stop_tcpprobe():
    Popen("killall -9 cat", shell=True).wait()

def start_qmon(iface, interval_sec=0.1, outfile="q.txt"):
    monitor = Process(target=monitor_qlen,args=(iface, interval_sec, outfile))
    monitor.start()
    return monitor

def start_webserver(net):
    h1 = net.getNodeByName('h1')
    proc = h1.popen("python http/webserver.py", shell=True)
    sleep(1)
    return [proc]


def timing_tester(net):
    print "starting timing testing"
    h1 = net.getNodeByName('h1')
    h2 = net.getNodeByName('h2')

    # Hint: have a separate function to do this and you may find the
    # loop below useful.
    exp_time = 25
    fetch_results = []
    start_time = time()
    while True:
        # do the measurement (say) 3 times.
        sleep(5)
        now = time()
        delta = now - start_time
        if delta > exp_time:
            break
        print "%.1fs left..." % (exp_time - delta)
        fetch = h2.popen("curl -o /dev/null -s -w %%{time_total} %s/http/index.html" % h1.IP())
        fetch.wait()
        fetch_results.append(fetch.communicate()[0])
    return fetch_results


def bufferbloat(**kwargs):
    # Linux uses CUBIC-TCP by default that doesn't have the usual sawtooth
    # behaviour.  For those who are curious, replace reno with cubic
    # see what happens...
    # sysctl -a | grep cong should list some interesting parameters.
    os.system("sysctl -w net.ipv4.tcp_congestion_control=reno")
    
    # create the topology and network
    topo = BBTopo(int(kwargs['queue_size']), int(kwargs['ping_RTT']))
    net = Mininet(topo=topo, host=CPULimitedHost, link=TCLink, controller= OVSController)
    net.start()

    # This dumps the topology and how nodes are interconnected through
    # links.
    dumpNodeConnections(net.hosts)
    
    # This performs a basic all pairs ping test.
    net.pingAll()
    
    # Start all the monitoring processes
    start_tcpprobe("cwnd.txt")

    # TODO: Start monitoring the queue sizes.  Since the switch I
    # created is "s0", I monitor one of the interfaces.  Which
    # interface?  The interface numbering starts with 1 and increases.
    # Depending on the order you add links to your network, this
    # number may be 1 or 2.  Ensure you use the correct number.
    # qmon = start_qmon(...)    
    qmon = start_qmon(iface='s0-eth2', outfile='%s/q.txt' % ".")

    # TODO: Start iperf, pings, and the webserver.
    # start_iperf(net), ...
    start_iperf(net, kwargs['congestion_window'])
    start_webserver(net)
    start_ping(net)

    # TODO: measure the time it takes to complete webpage transfer
    # from h1 to h2 (say) 4-5 times.  Hint: check what the following
    # command does: curl -o /dev/null -s -w %{time_total} google.com
    # Now use the curl command to fetch webpage from the webserver you
    # spawned on host h1 (not from google!)
    print "starting timing tester"
    timing_results = timing_tester(net)

    # TODO: compute average (and standard deviation) of the fetch
    # times.  You don't need to plot them.  Just print them
    # here and explain your observations in the Questions part
    # in Part 2, where you analyze your measurements.
    print timing_results[0]
    print "Ave fetching time:  %.4f" % numpy.average(numpy.array(timing_results).astype(numpy.float))
    print "std dev. of fetching times: %.4f" % numpy.std(numpy.array(timing_results).astype(numpy.float))

    # Stop probing 
    stop_tcpprobe()
    qmon.terminate()
    net.stop()
    
    # Ensure that all processes you create within Mininet are killed.
    # Sometimes they require manual killing.
    Popen("pgrep -f webserver.py | xargs kill -9", shell=True).wait()

if __name__ == "__main__":
    call(["mn", "-c"])
    print "starting bufferbloat()... \n\n"
    queue_size = sys.argv[1]
    congestion_window = sys.argv[2]
    ping_RTT = sys.argv[3]
    bufferbloat(queue_size=queue_size,congestion_window=congestion_window, ping_RTT=ping_RTT)
    windowgraph.plot_congestion_window("cwnd.txt")
    windowgraph.plot_queue_length("q.txt")
    windowgraph.plot_ping_rtt("pingoutput.txt")

