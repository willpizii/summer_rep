Scripts for analysing overlap and separation in QGIS between fault pairs

fullworkflow.py

Can be run in fully or partially automatic mode - with or without an input polygon for overlap/separation

Select two faults in an input layer to analyse

set input layer name on line 25 - input_layer_name = 'FAULT_LAYER' 
NOTE - requires fault layer to be in a projection with metres as units

set depth = DEPTH 
NOTE - no effect aside from output name

If in fully automatic mode:
	set polygon_mode = False on line 27

	The script will create a polygon from the transect line generated from each of the selected faults of length 'length'
	If no valid quadrilaterals are created, it will try projections from each fault in turn
	If no valid polygons are created, it will create the bounding polygon created by the two faults

If passing an input polygon:
	set polygon_mode = True on line 29
	set input_polygone_name = 'poly' 
	NOTE - must be a layer containing one polygon in same projection as fault layer

When finding separation and overlap, the script may fail. Try decreasing 'interval' or check that a polygon between the faults has sides with perpendicular transects that meet inside the polygon

Not entirely reliable in generating correct names - need to fix the naming function logic for O and S - see lines 917--

But when works, will generate, for two faults Xfault and Yfault where X is north of Y:

0m_X_Y_S, 0m_X_Y_O, 0m_X_Y_poly

It can also account for when faults have similar names in an overall layer - i.e. if a layer contains faults named Obama, Orange and Olive:

output layers will be named with Ob, Ol, and Or

The script prints the mean and std dev of (what it thinks are) separation and overlap to console



scratchpoly.py

creates a quick polygon layer in a specified CRS. used to create overlap polygons for fullworkflow.py



quicktransect.py 

creates a quick transect layer from a selected line of named layer layer_name, of specified length transect_length
