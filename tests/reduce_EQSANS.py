#!/usr/bin/env python
import sys,os
sys.path.insert(0,"/opt/mantid50/bin")
sys.path.insert(1,"/opt/mantid50/lib")
from mantid.simpleapi import *
from matplotlib import *
use("agg")
from matplotlib.pyplot import *
from numpy import *
numpy.seterr(all='ignore')
import warnings
warnings.filterwarnings('ignore',module='numpy')

if __name__ == "__main__":    
    #check number of arguments
    if (len(sys.argv) != 3): 
        print("autoreduction code requires a filename and an output directory")
        sys.exit()
    if not(os.path.isfile(sys.argv[1])):
        print("data file ", sys.argv[1], " not found")
        sys.exit()
    else:
        filename = sys.argv[1]
        outdir = sys.argv[2]
        
    w=Load(filename)
    wi=Integration(w)
    data=wi.extractY().reshape(-1,8,256).T
    data2=data[:,[0,4,1,5,2,6,3,7],:]
    data2=data2.transpose().reshape(-1,256)
    Z=ma.masked_where(data2<1,data2)

    try:
        from postprocessing.publish_plot import plot_heatmap
    except ImportError:
        from finddata.publish_plot import plot_heatmap
    x=arange(192)+1
    y=arange(256)+1
    Z = np.log(np.transpose(Z))
    plot_heatmap(w.getRunNumber(), x.tolist(), y.tolist(), Z.tolist(), x_title='Tube', y_title='Pixel',
                 x_log=False, y_log=False, instrument='EQSANS', publish=True)

