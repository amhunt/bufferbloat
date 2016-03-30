#%matplotlib inline

from helper import *
from collections import defaultdict

import plot_defaults
from matplotlib.ticker import MaxNLocator
from pylab import figure

IPERF_PORT = '5001'

def first(lst):
    return map(lambda e: e[0], lst)

def second(lst):
    return map(lambda e: e[1], lst)

"""
Sample line:
2.221032535 10.0.0.2:39815 10.0.0.1:5001 32 0x1a2a710c 0x1a2a387c 11 2147483647 14592 85
"""
def parse_file(f):
    times = defaultdict(list)
    cwnd = defaultdict(list)
    srtt = []
    for l in open(f).xreadlines():
        fields = l.strip().split(' ')
        if len(fields) != 11:
            break
        if fields[2].split(':')[1] != IPERF_PORT:
            continue
        sport = int(fields[1].split(':')[1])
        times[sport].append(float(fields[0]))

        c = int(fields[6])
        cwnd[sport].append(c * 1480 / 1024.0)
        srtt.append(int(fields[-1]))
    return times, cwnd

def plot_cwnds(ax, f, events):
    times, cwnds = parse_file(f)
    for port in sorted(cwnds.keys()):
        t = times[port]
        cwnd = cwnds[port]

        events += zip(t, [port]*len(t), cwnd)
        ax.plot(t, cwnd)

    events.sort()

def plot_congestion_window(filename, histogram=False):    
    added = defaultdict(int)
    events = []
    total_cwnd = 0
    cwnd_time = []

    min_total_cwnd = 10**10
    max_total_cwnd = 0
    totalcwnds = []

    m.rc('figure', figsize=(16, 6))
    fig = plt.figure()
    plots = 1
    if histogram:
        plots = 2

    axPlot = fig.add_subplot(1, plots, 1)
    plot_cwnds(axPlot, filename, events)

    for (t,p,c) in events:
        if added[p]:
            total_cwnd -= added[p]
        total_cwnd += c
        cwnd_time.append((t, total_cwnd))
        added[p] = c
        totalcwnds.append(total_cwnd)

    axPlot.plot(first(cwnd_time), second(cwnd_time), lw=2, label="$\sum_i W_i$")
    axPlot.grid(True)
    #axPlot.legend()
    axPlot.set_xlabel("seconds")
    axPlot.set_ylabel("cwnd KB")
    axPlot.set_title("TCP congestion window (cwnd) timeseries")

    if histogram:
        axHist = fig.add_subplot(1, 2, 2)
        n, bins, patches = axHist.hist(totalcwnds, 50, normed=1, facecolor='green', alpha=0.75)

        axHist.set_xlabel("bins (KB)")
        axHist.set_ylabel("Fraction")
        axHist.set_title("Histogram of sum(cwnd_i)")

    plt.show()

def plot_queue_length(f):
    to_plot=[]
    m.rc('figure', figsize=(16, 6))
    fig = figure()
    ax = fig.add_subplot(111)
    
    data = read_list(f)
    xaxis = map(float, col(0, data))
    start_time = xaxis[0]
    xaxis = map(lambda x: x - start_time, xaxis)
    qlens = map(float, col(1, data))

    xaxis = xaxis[::1]
    qlens = qlens[::1]
    ax.plot(xaxis, qlens, lw=2, color = 'red')
    ax.xaxis.set_major_locator(MaxNLocator(4))

    plt.ylabel("Packets")
    plt.grid(True)
    plt.xlabel("Seconds")

    plt.show()

def parse_ping(fname):
    ret = []
    lines = open(fname).readlines()
    num = 0
    for line in lines:
        if 'bytes from' not in line:
            continue
        try:
            rtt = line.split(' ')[-2]
            rtt = rtt.split('=')[1]
            rtt = float(rtt)
            ret.append([num, rtt])
            num += 1
        except:
            break
    return ret

def plot_ping_rtt(f, freq=10):
    m.rc('figure', figsize=(16, 6))
    fig = figure()
    ax = fig.add_subplot(111)
    
    data = parse_ping(f)
    xaxis = map(float, col(0, data))
    start_time = xaxis[0]
    xaxis = map(lambda x: (x - start_time) / freq, xaxis)
    qlens = map(float, col(1, data))

    ax.plot(xaxis, qlens, lw=2)
    ax.xaxis.set_major_locator(MaxNLocator(4))

    plt.ylabel("RTT (ms)")
    plt.grid(True)

    plt.show()

