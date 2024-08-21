# Plot Notebooks

"plot.ipynb" exists in the same folder as a model output

- This will read model output and snapshot files

- Generates plots including the fault progression plot

- Useful for looking at the output of one specific model to understand it better

"comparison-pandas.ipynb" exists in a folder called 'comparison' while models exist in a folder at the same level called 'run'

- Pulls data excluding snapshots from all the models

- Creates various (too many) plots in space

- Adaptable to any number of output models, assuming they follow the naming convention 'mod_XXXx_YYYy_ZZZz' where XXX, YYY, ZZZ represent the model offsets in each direction

- Requires a definition model 'mod_def' of a single fault for some plots

- Outputs various csv as well, of events, slow events...
