import numpy as np
from scipy.signal.windows import cosine
import sys
import os
import shutil
import glob # gogabgalab
from scipy.ndimage import uniform_filter
import noise

from qdyn import qdyn
from qdyn.utils.pre_processing.fault_split import create_double_fault as split_fault

# Get the full path of the current script
file_path = __file__

# Extract the file name from the path
file_name = os.path.basename(file_path)

script_dir = os.path.dirname(file_path)
dir_name = os.path.basename(script_dir)

KEY = [int(sys.argv[1]),int(sys.argv[2]),int(sys.argv[3])]
print(f"X={KEY[0]}, Y={KEY[1]}, Z={KEY[2]}")

if file_name != f"in_{KEY[0]}x_{KEY[1]}y_{KEY[2]}z.py":
    raise ValueError(f"Check the input file name. This should be in_{KEY[0]}x_{KEY[1]}y_{KEY[2]}z.py and was found to be {file_name}")
elif dir_name != f"mod_{KEY[0]}x_{KEY[1]}y_{KEY[2]}z":
    raise ValueError(f"Check the input file name. This should be mod_{KEY[0]}x_{KEY[1]}y_{KEY[2]}z.py and was found to be {dir_name}")

# Instantiate the QDYN class object
p = qdyn()

# Predefine parameters
t_yr = 3600 * 24 * 365.0    # Seconds per year
L = 5e3                     # Length of fault along-strike
W = 6e3                     # Length of fault along-dip
resolution = 4              # Mesh resolution / process zone width

# Get the settings dict
set_dict = p.set_dict

t_restart = 2000*t_yr

""" Step 1: Define simulation/mesh parameters """
# Global simulation parameters
set_dict["MESHDIM"] = 2        # Simulation dimensionality (2D fault in 3D medium)
set_dict["FAULT_TYPE"] = -2    # Normal fault
set_dict["TMAX"] = t_restart      # Maximum simulation time [s]
set_dict["NTOUT"] = 20         # Save output every N steps
set_dict["NXOUT"] = 10          # Snapshot resolution along-strike (every N elements)
set_dict["NWOUT"] = 10          # Snapshot resolution along-dip (every N elements)
set_dict["V_PL"] = 1e-10        # Plate velocity
set_dict["MU"] = 3e10          # Shear modulus
set_dict["SIGMA"] = 43.6e6        # Effective normal stress [Pa] # will be rewritten after
set_dict["ACC"] = 1e-7         # Solver accuracy
set_dict["SOLVER"] = 2         # Solver type (Runge-Kutta)
set_dict["Z_CORNER"] = -6e3    # Base of the fault (depth taken <0)
set_dict["DIP_W"] = 60         # Dip of the fault
set_dict["FEAT_STRESS_COUPL"] = 1

# set_dict["OX_DYN"] = 1 # enable dynamic snapshots to record end of fault

# MPI parameters
# set_dict["MPI_PATH"] = "/opt/ohpc/pub/modulefiles_intel_oneAPI/mpi"
set_dict["NPROC"] = 1        # Number of cores (MPI tasks) for parallel computing

# setting indices of time-series output
set_dict["IOT"] = 0 # assign 1 to element of index i_element

# Setting some (default) RSF parameter values
set_dict["SET_DICT_RSF"]["A"] = 0.007    # Direct effect (will be overwritten later)
set_dict["SET_DICT_RSF"]["B"] = 0.014    # Evolution effect
set_dict["SET_DICT_RSF"]["DC"] = 2e-3     # Characteristic slip distance
set_dict["SET_DICT_RSF"]["V_SS"] = set_dict["V_PL"]    # Reference velocity [m/s]
set_dict["SET_DICT_RSF"]["V_0"] = set_dict["V_PL"]     # Initial velocity [m/s]
set_dict["SET_DICT_RSF"]["TH_0"] = 0.99 * set_dict["SET_DICT_RSF"]["DC"] / set_dict["V_PL"]    # Initial (steady-)state [s]

# Process zone width [m]
Lb = set_dict["MU"] * set_dict["SET_DICT_RSF"]["DC"] / (set_dict["SET_DICT_RSF"]["B"] * set_dict["SIGMA"])
# Nucleation length [m]
Lc = set_dict["MU"] * set_dict["SET_DICT_RSF"]["DC"] / ((set_dict["SET_DICT_RSF"]["B"] - set_dict["SET_DICT_RSF"]["A"]) * set_dict["SIGMA"])

print(f"Process zone size: {Lb} m \t Nucleation length: {Lc} m")

# Find next power of two for number of mesh elements along-strike
Nx = int(np.power(2, np.ceil(np.log2(resolution * L / Lb))))
# Along-dip direction doesn't need to be a power of 2
Nw = int(resolution * W / Lb)

# Set mesh size and fault length
set_dict["NX"] = Nx
set_dict["NW"] = Nw
set_dict["L"] = L
set_dict["W"] = W
# Set time series output node to the middle of the fault
set_dict["IC"] = Nx * (Nw // 2) + Nx // 2

""" Step 2: Set (default) parameter values and generate mesh """
p.settings(set_dict)
p.render_mesh() # setting also the coordinates without the need to explicitly setting them


dip = set_dict["DIP_W"]
# Create a vector of mesh element spacings
# dw = np.ones(Nw) * (W / Nw)
# dw[split:] = 0.5 * (W / Nw)
dw = W/Nw

# Override the default mesh with these new dip/spacing values
p.compute_mesh_coords(p.mesh_dict, dip, dw)

p = split_fault(p, KEY[0], KEY[1], KEY[2], 0.6e3, 0, 0.5e3)

########################
# Modify normal stress #
########################

# using profile of Lapusta et al. (2000)
sigma1 = np.full(len(p.mesh_dict["Z"]), 50e6)
sigma2 = (2.8 + 18*-p.mesh_dict["Z"]/1000)*1e6
sigma_v = [min(els) for els in zip(sigma1, sigma2)]

# account for dip angle
sigma = np.sin(np.radians(set_dict["DIP_W"]))*np.array(sigma_v)

# override sigma values
p.mesh_dict["SIGMA"] = sigma

##################################
# Output indices for time series #
##################################
i1 = p.set_dict["NW"]//4*p.set_dict["NX"] - p.set_dict["NX"]//2 # index of element in the center of Fault 1
i2 = p.set_dict["NW"]*3//4*p.set_dict["NX"] - p.set_dict["NX"]//2 # index of element in the center of Fault 2

v_i = np.zeros(set_dict["N"]) #vector of length N with 0s
v_i[i1]=1 # replace value by 1 in the ith element
v_i[i2]=1 # replace value by 1 in the ith element

p.mesh_dict["IOT"]=v_i #override IOT vector

###############
# Write input #
###############


# Write input to qdyn.in
p.write_input()

#####################
# Save dict as file #
#####################

# load pickle module
import pickle

# define dictionary
dict = p.mesh_dict

# create a binary pickle file (output file)
f = open("meshdict.pkl","wb")

# write the python object (dict) to pickle file
pickle.dump(dict,f)

# close file
f.close()

# define dictionary
dict2 = p.set_dict

# create a binary pickle file (output file)
f = open("setdict.pkl","wb")

# write the python object (dict) to pickle file
pickle.dump(dict2,f)

# close file
f.close()
