to generate new models:

(0: clear out all old model files if needed)
1: change the values in the x and y arrays in the shell script to appropriate values
2: run 'sh create.sh' on the terminal
3: voila

DO NOT remove or rename template.py

To change the generated models, you can change the python script called in create.sh

template.py - default, smoothed corners model
templaterp.py - original rectangular model by CRP
circletemplate.py - circular asperity, as in example QDYN notebook
experiments/template_smooth.py - changes loading velocity across overlap region, so sum of velocity across strike is constant

Running create.sh will depend on being in an appropriate conda environment, with loaded modules as required by each python script

The QDYN version loaded must be that from the the main release/3.0.0 branch of https://github.com/willpizii/qdyn
