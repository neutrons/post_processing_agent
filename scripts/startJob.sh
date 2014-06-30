#!/bin/bash
# Usage: startJob.sh <path to processing script> <destination> <data> 
module load mantid-mpi
python $1 -q $2 -d $3
