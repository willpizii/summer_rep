#!/bin/bash

x_arr+=(0 1000 2000 2500 3000 3500 4000 5000)
y_arr+=(1500)
z=0

for x in "${x_arr[@]}"
do
    for y in "${y_arr[@]}"
    do
        # Format the directory name
        dir_name="mod_${x}x_${y}y_${z}z"
        file_name="in_${x}x_${y}y_${z}z.py"

        # Print the directory name for debugging
        echo "Creating directory: $dir_name"

        # Create the directory
        mkdir "$dir_name"

        cp template.py $dir_name/$file_name

        cd $dir_name
        python $file_name $x $y $z

        echo "Created input file: $file_name"
	echo ""
        cd ..

    done
done
