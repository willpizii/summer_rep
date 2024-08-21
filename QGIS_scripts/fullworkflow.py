from qgis.core import QgsProject,QgsCoordinateReferenceSystem, QgsCoordinateTransformContext, QgsExpression, QgsExpressionContextUtils, QgsExpressionContext, QgsVectorLayer, QgsFeature, QgsGeometry, QgsPoint, QgsField, QgsProcessingFeedback, QgsApplication
from qgis.core import (
    QgsProject,
    QgsFeature,
    QgsGeometry,
    QgsVectorLayer,
    QgsLineString,
    QgsPoint,
    QgsFields,
    QgsField,
    QgsWkbTypes,
    QgsFeatureSink,
    QgsCoordinateReferenceSystem
)
from PyQt5.QtCore import QVariant
import processing
import math
from statistics import mean, stdev
depth = 0
interval = 100
buffer_distance = 1000

compatibility = False # by default. 'compatibility' is True when no intersections with transects found

input_layer_name = 'ca_rect'  # Replace with your actual layer name

polygon_mode = True
if polygon_mode:
    input_polygon_name = 'poly'
    input_poly_layer = QgsProject.instance().mapLayersByName(input_polygon_name)[0]

# Retrieve the layer from the QGIS project
input_layer = QgsProject.instance().mapLayersByName(input_layer_name)[0]


# Ensure the layer is valid
if not input_layer:
    raise Exception(f"Layer '{input_layer_name}' not found in the project.")

# Ensure the layer has selected features
if input_layer.selectedFeatureCount() != 2:
    raise Exception("Need 2 selected features in the input layer.")
crs = input_layer.crs()

length = 50000

selected_features_layer = QgsVectorLayer('LineString?crs=' + input_layer.crs().authid(), 'selected_features', 'memory')
selected_features_provider = selected_features_layer.dataProvider()
selected_features_provider.addAttributes(input_layer.fields())
selected_features_layer.updateFields()

for feature in input_layer.selectedFeatures():
    selected_features_provider.addFeature(feature)

if not polygon_mode:

    transparams = {
        'INPUT': selected_features_layer,
        'LENGTH': length,
        'SIDE': 2,  # 2 for both sides
        'ANGLE': 90,
        'OUTPUT': 'memory:'
    }

    transects = processing.run("native:transect", transparams, feedback=QgsProcessingFeedback())
    translayer = transects['OUTPUT']
        
    merge_params = {
        'LAYERS': [selected_features_layer, translayer],
        'CRS': crs.authid(),  # Use the CRS of the first layer
        'OUTPUT': 'memory:'  # Output as an in-memory layer
    }

    # Run the merge vector layers algorithm
    merged_layer = processing.run("native:mergevectorlayers", merge_params)['OUTPUT']

    lines_to_polygons_params = {
        'INPUT': merged_layer,
        'CRS': crs.authid(),
        'OUTPUT': 'memory:'  # Output as an in-memory layer
    }

    # Run the lines to polygons algorithm
    polygons_layer = processing.run("native:polygonize", lines_to_polygons_params)['OUTPUT']

    # QgsProject.instance().addMapLayer(polygons_layer)

    line_features = list(selected_features_layer.getFeatures())
    polygon_feature = next(polygons_layer.getFeatures())
    polygon_geometry = polygon_feature.geometry()

    def create_polygon_from_lines(line1, line2):
        # Check the type of the geometries
        wkb_type1 = line1.wkbType()
        wkb_type2 = line2.wkbType()

        if wkb_type1 == wkb_type2:
            if wkb_type1 == 1005:
                lines1 = line1.asMultiPolyline()
                lines2 = line2.asMultiPolyline()
                withZ = True
            elif wkb_type1 == 1002:
                lines1 = [line1.asPolyline()]
                lines2 = [line2.asPolyline()]
                withZ = True
            elif wkb_type1 == 5:
                lines1 = line1.asMultiPolyline()
                lines2 = line2.asMultiPolyline()
                withZ = False
            elif wkb_type1 == 2:
                lines1 = [line1.asPolyline()]
                lines2 = [line2.asPolyline()]
                withZ = False
            else:
                raise TypeError(f"Unsupported geometry type - {wkb_type1}")
        else:
            raise TypeError(f"Selected lines are of different types - {wkb_type1}, {wkb_type2}")

        # Extract vertices from the lines
        def convert_to_2d(lines):
            converted = []
            for line in lines:
                for point in line:
                    converted.append(QgsPointXY(point.x(), point.y()))
            return converted

        # Process lines and collect vertices
        vertices1_2d = convert_to_2d(lines1) if withZ else [point for line in lines1 for point in line]
        vertices2_2d = convert_to_2d(lines2) if withZ else [point for line in lines2 for point in line]

        # Combine vertices from both lines
        combined_vertices = vertices1_2d + vertices2_2d[::-1]  # Reverse the second line to form a closed shape
        combined_vertices.append(vertices1_2d[0])  # Close the polygon

        # Create a QgsPolygon geometry
        polygon_geometry = QgsGeometry.fromPolygonXY([combined_vertices])

        return polygon_geometry

    clipper = create_polygon_from_lines(line_features[0].geometry(),
                                        line_features[1].geometry())

    buffer_distance = 1000
    reference_features = []
    geom = clipper
    buffered_geom = geom.buffer(buffer_distance, 5)  # 5 is the number of segments per quarter circle
    reference_features.append(buffered_geom)

    def is_wholly_contained(inner_geom, outer_geom):
        if outer_geom.contains(inner_geom):
            return True
        return False

    # QgsProject.instance().addMapLayer(polygons_layer) # debug
    polygons_layer.startEditing()
    # Create a list to hold IDs of features to delete
    features_to_delete = []
    for feature in polygons_layer.getFeatures():
        geometry = feature.geometry()
        if geometry.isEmpty():
            continue
        
        # Extract the polygon's vertices
        vertices = geometry.asPolygon()[0]  # Assumes single-part polygons
        if len(vertices) != 5:
            features_to_delete.append(feature.id())
            continue
            
        if not is_wholly_contained(geometry, reference_features[0]):
            features_to_delete.append(feature.id())


    # Delete the features

    if features_to_delete and len(features_to_delete) != len(list(polygons_layer.getFeatures())):
        polygons_layer.dataProvider().deleteFeatures(features_to_delete)
        polygons_layer.commitChanges()
        print(f"Deleted {len(features_to_delete)} features.")
    elif len(features_to_delete) == len(list(polygons_layer.getFeatures())) or len(list(polygons_layer.getFeatures())) > 1:
        # raise Exception("Attempted to delete all features!")
        print("No valid polygons from both transects! Attempting in turn")
        ## OVERRIDE the default polygon maker - transect from each fault in turn and see if polygons exist!
        del polygons_layer

        for i in [0,1]:
            selected_features_layer2 = QgsVectorLayer('LineString?crs=' + input_layer.crs().authid(), 'selected_features', 'memory')
            selected_features_provider2 = selected_features_layer2.dataProvider()
            selected_features_provider2.addAttributes(input_layer.fields())
            selected_features_layer2.updateFields()

            selected_features2 = input_layer.selectedFeatures()
            #print(list(selected_features2))
            if selected_features2:
                selected_features_provider2.addFeature(selected_features2[i])
                #print(selected_features2[i])
                
            transparams = {
                'INPUT': selected_features_layer2,
                'LENGTH': length,
                'SIDE': 2,  # 2 for both sides
                'ANGLE': 90,
                'OUTPUT': 'memory:'
            }

            transects = processing.run("native:transect", transparams, feedback=QgsProcessingFeedback())
            translayer = transects['OUTPUT']
                
            merge_params = {
                'LAYERS': [selected_features_layer, translayer],
                'CRS': crs.authid(),  # Use the CRS of the first layer
                'OUTPUT': 'memory:'  # Output as an in-memory layer
            }

            # Run the merge vector layers algorithm
            merged_layer = processing.run("native:mergevectorlayers", merge_params)['OUTPUT']

            lines_to_polygons_params = {
                'INPUT': merged_layer,
                'CRS': crs.authid(),
                'OUTPUT': 'memory:'  # Output as an in-memory layer
            }

            # Run the lines to polygons algorithm
            polygons_layers = processing.run("native:polygonize", lines_to_polygons_params)['OUTPUT']
            if len(list(polygons_layers.getFeatures())) == 0:
                print(f'No intersection from fault {i}')
                if i == 1:
                    polygons_layer = []
                continue
            else:
                polygons_layer = polygons_layers
            QgsProject.instance().addMapLayer(polygons_layer)

            line_features = list(selected_features_layer.getFeatures())
            polygon_feature = next(polygons_layer.getFeatures())
            polygon_geometry = polygon_feature.geometry()

            def create_polygon_from_lines(line1, line2):
                # Check the type of the geometries
                wkb_type1 = line1.wkbType()
                wkb_type2 = line2.wkbType()

                if wkb_type1 == wkb_type2:
                    if wkb_type1 == 1005:
                        lines1 = line1.asMultiPolyline()
                        lines2 = line2.asMultiPolyline()
                        withZ = True
                    elif wkb_type1 == 1002:
                        lines1 = [line1.asPolyline()]
                        lines2 = [line2.asPolyline()]
                        withZ = True
                    elif wkb_type1 == 5:
                        lines1 = line1.asMultiPolyline()
                        lines2 = line2.asMultiPolyline()
                        withZ = False
                    elif wkb_type1 == 2:
                        lines1 = [line1.asPolyline()]
                        lines2 = [line2.asPolyline()]
                        withZ = False
                    else:
                        raise TypeError(f"Unsupported geometry type - {wkb_type1}")
                else:
                    raise TypeError(f"Selected lines are of different types - {wkb_type1}, {wkb_type2}")

                # Extract vertices from the lines
                def convert_to_2d(lines):
                    converted = []
                    for line in lines:
                        for point in line:
                            converted.append(QgsPointXY(point.x(), point.y()))
                    return converted

                # Process lines and collect vertices
                vertices1_2d = convert_to_2d(lines1) if withZ else [point for line in lines1 for point in line]
                vertices2_2d = convert_to_2d(lines2) if withZ else [point for line in lines2 for point in line]

                # Combine vertices from both lines
                combined_vertices = vertices1_2d + vertices2_2d[::-1]  # Reverse the second line to form a closed shape
                combined_vertices.append(vertices1_2d[0])  # Close the polygon

                # Create a QgsPolygon geometry
                polygon_geometry = QgsGeometry.fromPolygonXY([combined_vertices])

                return polygon_geometry

            clipper = create_polygon_from_lines(line_features[0].geometry(),
                                                line_features[1].geometry())

            buffer_distance = 1000
            reference_features = []
            geom = clipper
            buffered_geom = geom.buffer(buffer_distance, 5)  # 5 is the number of segments per quarter circle
            reference_features.append(buffered_geom)

            def is_wholly_contained(inner_geom, outer_geom):
                if outer_geom.contains(inner_geom):
                    return True
                return False
            
            #polygons_layer.setName(f"{i}_poly")
            #QgsProject.instance().addMapLayer(polygons_layer) # debug
            polygons_layer.startEditing()
            # Create a list to hold IDs of features to delete
            features_to_delete = []
            for feature in polygons_layer.getFeatures():
                geometry = feature.geometry()
                if geometry.isEmpty():
                    continue
                
                # Extract the polygon's vertices
                vertices = geometry.asPolygon()[0]  # Assumes single-part polygons
                if len(vertices) != 5:
                    features_to_delete.append(feature.id())
                    continue
                    
                if not is_wholly_contained(geometry, reference_features[0]):
                    features_to_delete.append(feature.id())
            
            polygons_layer.commitChanges()
            print(f'Overwrote new polygon with feature {i}')
        
        if not polygons_layer or len(list(polygons_layer.getFeatures())) != 1:
            if polygons_layer and len(list(polygons_layer.getFeatures())) != 1:
                if not polygon_mode:
                    raise Exception("Geometry still invalid!")
            # raise Exception("Still cannot get required amount of features. Check faults overlap!")
            del polygons_layer

            # Create a new memory layer with Polygon geometry
            polygons_layer = QgsVectorLayer('Polygon?crs=' + input_layer.crs().authid(),'', 'memory')
            
            polygons_provider = polygons_layer.dataProvider()

            polygons_feature = QgsFeature()

            # Set the geometry of the feature to the clipper geometry
            polygons_feature.setGeometry(clipper.buffer(0,0))
            result = polygons_provider.addFeature(polygons_feature)

            # Check if the feature was added successfully
            polygons_layer.updateExtents()
            print("NOTE: Taking total polygon area! O/S values less comparable!")
            
            compatibility = True

    else:
        polygons_layer.rollBack()  # Roll back if no features were deleted
        print("No features to delete.")
        
    polygons_layer.commitChanges()

if polygon_mode:
    del polygons_layer
    polygons_layer = input_poly_layer

line_features = list(selected_features_layer.getFeatures())
polygon_feature = next(polygons_layer.getFeatures())
polygon_geometry = polygon_feature.geometry()
# Extract intersection points and determine which line is more northern
northern_line = None
northern_point = None
southern_line = None
southern_point = None

eastern_line = None
eastern_point = None
western_line = None
western_point = None

# Function to update the northernmost point if applicable
def update_northern_point(point, line_feature):
    global northern_point, northern_line
    if northern_point is None or point.y() > northern_point.y():
        northern_point = point
        
        if northern_line != line_feature:
            print("N line updated")
        
        northern_line = line_feature

def update_southern_point(point, line_feature):
    global southern_point, southern_line
    if southern_point is None or point.y() < southern_point.y():
        southern_point = point
        
        if southern_line != line_feature:
            print("S line updated")
        
        southern_line = line_feature
        
def update_eastern_point(point, line_feature):
    global eastern_point, eastern_line
    if eastern_point is None or point.x() > eastern_point.x():
        eastern_point = point
        eastern_line = line_feature

def update_western_point(point, line_feature):
    global western_point, western_line
    if western_point is None or point.x() < western_point.x():
        western_point = point
        western_line = line_feature

denslineparams = {
        'INPUT': selected_features_layer,
        'INTERVAL': interval,
        'OUTPUT': 'memory:'
    }
denselect = processing.run("qgis:densifygeometriesgivenaninterval", denslineparams, feedback=QgsProcessingFeedback())
denselectlayer = denselect['OUTPUT']

for line_feature in line_features:
    line_geometry = line_feature.geometry()
    print(line_feature['name'])
    # Find intersections between the line and the polygon
    intersection_geometry = line_geometry.intersection(polygon_geometry.buffer(buffer_distance, 5))
    if intersection_geometry.isEmpty():
        print("No intersection!")
        continue
    print(intersection_geometry.wkbType())
    
    # handle the case where for some reason the line strings have z values
    def convert_multi_line_string_z_to_multi_line_string(geom):
        if geom.wkbType() == QgsWkbTypes.MultiLineStringZ:
            line_strings = []

            # Extract the geometries from the MultiLineStringZ
            geometries = geom.asGeometryCollection()

            for geometry in geometries:
                if geometry.wkbType() == QgsWkbTypes.LineStringZ:
                    # Convert each 3D LineStringZ to a 2D LineString
                    line_string_z = geometry.asPolyline()
                    line_string_2d = [QgsPointXY(point.x(), point.y()) for point in line_string_z]
                    # Create a QgsLineString (2D) and add it to the list
                    line_strings.append(QgsLineString(line_string_2d))

            # Create a QgsMultiLineString from the 2D QgsLineString objects
            multi_line_string = QgsMultiLineString()
            for line_string in line_strings:
                multi_line_string.addGeometry(line_string)

            # Wrap the QgsMultiLineString in a QgsGeometry
            return QgsGeometry(multi_line_string)
        else:
            raise TypeError("Input geometry is not of type MultiLineStringZ")

    if intersection_geometry.wkbType() == QgsWkbTypes.MultiLineStringZ:
        intersection_geometry = convert_multi_line_string_z_to_multi_line_string(intersection_geometry)
    
    if intersection_geometry.wkbType() in [
        QgsWkbTypes.LineString,
        QgsWkbTypes.LineStringZ,
        QgsWkbTypes.MultiLineString,
        QgsWkbTypes.MultiLineStringZ,
        QgsWkbTypes.Point,
        QgsWkbTypes.PointZ,
        QgsWkbTypes.GeometryCollection
    ]:
        if intersection_geometry.wkbType() != QgsWkbTypes.GeometryCollection:
            geometries = intersection_geometry.asGeometryCollection()
        else:
            geometries = [intersection_geometry]
        
        # Check if the intersection is a LineString or MultiLineString
        for geom in geometries:
            if geom.wkbType() == QgsWkbTypes.LineString:
                # Extract points from the LineString
                line = geom.asPolyline()                
                for point in line:
                    update_northern_point(point, line_feature)
                    update_southern_point(point, line_feature)
                    
            elif geom.wkbType() == QgsWkbTypes.LineStringZ:
                # Extract points from the LineString
                line = geom.asPolyline()                
                for point in line:
                    update_northern_point(point, line_feature)
                    update_southern_point(point, line_feature)
                    
            elif geom.wkbType() == QgsWkbTypes.MultiLineString:
                # Extract points from each LineString in the MultiLineString
                for sub_geom in geom.asMultiLineString():
                    for point in sub_geom:
                        update_northern_point(point, line_feature)
                        update_southern_point(point, line_feature)
            
            elif geom.wkbType() == QgsWkbTypes.MultiLineStringZ:
                # Extract points from each LineString in the MultiLineString
                for sub_geom in geom.asMultiLineString():
                    for point in sub_geom:
                        update_northern_point(point, line_feature)
                        update_southern_point(point, line_feature)
                        
            elif geom.wkbType() == QgsWkbTypes.Point:
                # Handle the Point geometry directly
                point = geom.asPoint()  # This returns a QgsPoint, not a list
                update_northern_point(point, line_feature)
                update_southern_point(point, line_feature)
            
            elif geom.wkbType() == QgsWkbTypes.PointZ:
                # Handle the Point geometry directly
                point = geom.asPoint()  # This returns a QgsPoint, not a list
                update_northern_point(point, line_feature)
                update_southern_point(point, line_feature)
            
            elif geom.wkbType() == QgsWkbTypes.GeometryCollection:
                # Recursively handle GeometryCollection
                for sub_geom in geom.asGeometryCollection():
                    if sub_geom.wkbType() == QgsWkbTypes.LineString:
                        line = sub_geom.asPolyline()
                        for point in line:
                            update_northern_point(point, line_feature)
                            update_southern_point(point, line_feature)
                            
                    elif sub_geom.wkbType() == QgsWkbTypes.MultiLineString:
                        for line in sub_geom.asMultiLineString():
                            for point in line:
                                update_northern_point(point, line_feature)
                                update_southern_point(point, line_feature)
                                
                    elif sub_geom.wkbType() == QgsWkbTypes.Point:
                        point = sub_geom.asPoint()
                        update_northern_point(point, line_feature)
                        update_southern_point(point, line_feature)
                            
N_fault = northern_line['name']
S_fault = southern_line['name']

if S_fault == N_fault:
    print("Same result obtained from N and S analysis. Trying E-W...")
    
    for line_feature in line_features:
        line_geometry = line_feature.geometry()
        print(line_feature['name'])
        
        # Find intersections between the line and the polygon
        intersection_geometry = line_geometry.intersection(polygon_geometry.buffer(buffer_distance, 5))
        if intersection_geometry.isEmpty():
            continue
        print(intersection_geometry.wkbType())
        
        # Handle the case where the line strings have z values
        def convert_multi_line_string_z_to_multi_line_string(geom):
            if geom.wkbType() == QgsWkbTypes.MultiLineStringZ:
                line_strings = []

                # Extract the geometries from the MultiLineStringZ
                geometries = geom.asGeometryCollection()

                for geometry in geometries:
                    if geometry.wkbType() == QgsWkbTypes.LineStringZ:
                        # Convert each 3D LineStringZ to a 2D LineString
                        line_string_z = geometry.asPolyline()
                        line_string_2d = [QgsPointXY(point.x(), point.y()) for point in line_string_z]
                        # Create a QgsLineString (2D) and add it to the list
                        line_strings.append(QgsLineString(line_string_2d))

                # Create a QgsMultiLineString from the 2D QgsLineString objects
                multi_line_string = QgsMultiLineString()
                for line_string in line_strings:
                    multi_line_string.addGeometry(line_string)

                # Wrap the QgsMultiLineString in a QgsGeometry
                return QgsGeometry(multi_line_string)
            else:
                raise TypeError("Input geometry is not of type MultiLineStringZ")

        if intersection_geometry.wkbType() == QgsWkbTypes.MultiLineStringZ:
            intersection_geometry = convert_multi_line_string_z_to_multi_line_string(intersection_geometry)
        
        if intersection_geometry.wkbType() in [
            QgsWkbTypes.LineString,
            QgsWkbTypes.LineStringZ,
            QgsWkbTypes.MultiLineString,
            QgsWkbTypes.MultiLineStringZ,
            QgsWkbTypes.Point,
            QgsWkbTypes.PointZ,
            QgsWkbTypes.GeometryCollection
        ]:
            if intersection_geometry.wkbType() != QgsWkbTypes.GeometryCollection:
                geometries = intersection_geometry.asGeometryCollection()
            else:
                geometries = [intersection_geometry]
            
            # Check if the intersection is a LineString or MultiLineString
            for geom in geometries:
                if geom.wkbType() == QgsWkbTypes.LineString:
                    # Extract points from the LineString
                    line = geom.asPolyline()                
                    for point in line:
                        update_eastern_point(point, line_feature)
                        update_western_point(point, line_feature)
                        
                elif geom.wkbType() == QgsWkbTypes.LineStringZ:
                    # Extract points from the LineString
                    line = geom.asPolyline()                
                    for point in line:
                        update_eastern_point(point, line_feature)
                        update_western_point(point, line_feature)
                        
                elif geom.wkbType() == QgsWkbTypes.MultiLineString:
                    # Extract points from each LineString in the MultiLineString
                    for sub_geom in geom.asMultiLineString():
                        for point in sub_geom:
                            update_eastern_point(point, line_feature)
                            update_western_point(point, line_feature)
                
                elif geom.wkbType() == QgsWkbTypes.MultiLineStringZ:
                    # Extract points from each LineString in the MultiLineString
                    for sub_geom in geom.asMultiLineString():
                        for point in sub_geom:
                            update_eastern_point(point, line_feature)
                            update_western_point(point, line_feature)
                            
                elif geom.wkbType() == QgsWkbTypes.Point:
                    # Handle the Point geometry directly
                    point = geom.asPoint()  # This returns a QgsPoint, not a list
                    update_eastern_point(point, line_feature)
                    update_western_point(point, line_feature)
                
                elif geom.wkbType() == QgsWkbTypes.PointZ:
                    # Handle the Point geometry directly
                    point = geom.asPoint()  # This returns a QgsPoint, not a list
                    update_eastern_point(point, line_feature)
                    update_western_point(point, line_feature)
                
                elif geom.wkbType() == QgsWkbTypes.GeometryCollection:
                    # Recursively handle GeometryCollection
                    for sub_geom in geom.asGeometryCollection():
                        if sub_geom.wkbType() == QgsWkbTypes.LineString:
                            line = sub_geom.asPolyline()
                            for point in line:
                                update_eastern_point(point, line_feature)
                                update_western_point(point, line_feature)
                                
                        elif sub_geom.wkbType() == QgsWkbTypes.MultiLineString:
                            for line in sub_geom.asMultiLineString():
                                for point in line:
                                    update_eastern_point(point, line_feature)
                                    update_western_point(point, line_feature)
                                    
                        elif sub_geom.wkbType() == QgsWkbTypes.Point:
                            point = sub_geom.asPoint()
                            update_eastern_point(point, line_feature)
                            update_western_point(point, line_feature)
                            
    N_fault = eastern_line['name']
    S_fault = western_line['name']
    
    if N_fault == S_fault:
        print("Same result in E-W direction. Overriding")
        #print(eastern_point,"on",eastern_line)
        #print(western_point,"on",western_line)
        S_fault = 'Xfault'
# print(N_fault,f'\n', S_fault)

strikes = [f['STRIKEAVG']%180 for f in selected_features_layer.getFeatures()]
mean_strikes = mean(strikes)

line_layer = QgsVectorLayer(f"LineString?crs={crs.authid()}", "Quadrilateral Lines", "memory")
line_provider = line_layer.dataProvider()

# Define the fields (attributes) for the layer
fields = QgsFields()
fields.append(QgsField("id", QVariant.Int))
line_provider.addAttributes(fields)
line_layer.updateFields()

line_layer2 = QgsVectorLayer(f"LineString?crs={crs.authid()}", "Quadrilateral Lines", "memory")
line_provider2 = line_layer2.dataProvider()

# Define the fields (attributes) for the layer
fields2 = QgsFields()
fields2.append(QgsField("id", QVariant.Int))
line_provider2.addAttributes(fields2)
line_layer2.updateFields()

# Iterate through selected features in the input layer
itervar = 1

for feature in polygons_layer.getFeatures():
    geometry = feature.geometry()
    # print(geometry)
    vertices = geometry.asPolygon()[0]
    # Extract the quadrilateral's vertices (ignore the last vertex as it repeats the first)
    p1, p2, p3, p4 = vertices[0], vertices[1], vertices[2], vertices[3]

    # Create the opposite lines
    lines = [
        QgsLineString([p1, p2]),  # Diagonal from p1 to p3
        QgsLineString([p3, p4])   # Diagonal from p2 to p4
    ]
    # print(lines)
    # Add the lines to the layer
    for i, line in enumerate(lines):
        line_feature = QgsFeature()
        line_feature.setGeometry(QgsGeometry.fromPolyline(line))
        line_feature.setAttributes([i + 1])
        line_provider.addFeature(line_feature)
    
    lines = [
        QgsLineString([p2, p3]),  # Diagonal from p1 to p3
        QgsLineString([p4, p1])   # Diagonal from p2 to p4
    ]

    # Add the lines to the layer
    for i, line in enumerate(lines):
        line_feature = QgsFeature()
        line_feature.setGeometry(QgsGeometry.fromPolyline(line))
        line_feature.setAttributes([i + 1])
        line_provider2.addFeature(line_feature)

# Update the extents of the layer to include the new features
line_layer.updateExtents()
line_layer2.updateExtents()

crs_line_1 = processing.run(
        "native:reprojectlayer",
        {
            'INPUT': line_layer,
            'TARGET_CRS': crs,
            'OUTPUT': 'memory:'  # Output as in-memory layer
        }
    )['OUTPUT']

crs_line_1.updateExtents()
    
crs_line_2 = processing.run(
        "native:reprojectlayer",
        {
            'INPUT': line_layer2,
            'TARGET_CRS': crs,
            'OUTPUT': 'memory:'  # Output as in-memory layer
        }
    )['OUTPUT']

crs_line_2.updateExtents()

length = 60000

#QgsProject.instance().addMapLayer(crs_line_2)
#QgsProject.instance().addMapLayer(crs_line_1)

for inputter_layer in [crs_line_1, crs_line_2]:
    # densify
    densparams = {
        'INPUT': inputter_layer,
        'INTERVAL': interval,
        'OUTPUT': 'memory:'
    }
    densified = processing.run("qgis:densifygeometriesgivenaninterval", densparams, feedback=QgsProcessingFeedback())
    denslayer = densified['OUTPUT']
    del densified

    # transects
    transparams = {
        'INPUT': denslayer,
        'LENGTH': length,
        'SIDE': 2,  # 2 for both sides
        'ANGLE': 90,
        'OUTPUT': 'memory:'
    }

    try:
        transects = processing.run("native:transect", transparams, feedback=QgsProcessingFeedback())
        translayer = transects['OUTPUT']
    except Exception as e:
        print(f"Error in transect creation: {e}")

    layer_1 = translayer
    layer_2 = inputter_layer

    layer_1.startEditing()

    # Create a list to hold IDs of features to delete
    features_to_delete = []

    # Iterate over features in the first layer
    for feature_1 in layer_1.getFeatures():
        geometry_1 = feature_1.geometry()
        intersection_count = 0
        # Check intersections with features in the second layer
        for feature_2 in layer_2.getFeatures():
            geometry_2 = feature_2.geometry()
            if geometry_1.intersects(geometry_2):
                intersection_count += 1
            # if the feature intersects both lines, keep it
            if intersection_count == 2:
                break

        # delete lines that don't intersect both
        if intersection_count < 2:
            features_to_delete.append(feature_1.id())

    # delete non-intersecting lines from the layer
    if features_to_delete:
        layer_1.deleteFeatures(features_to_delete)

    # Commit the changes to the layer
    layer_1.commitChanges()

    reproj_selected_geom_provider = processing.run(
        "native:reprojectlayer",
        {
            'INPUT': polygons_layer,
            'TARGET_CRS': crs,
            'OUTPUT': 'memory:'  # Output as in-memory layer
        }
    )['OUTPUT']

    reproj_selected_geom_provider.updateExtents()

    params = {
        'INPUT': layer_1,
        'OVERLAY': reproj_selected_geom_provider,
        'OUTPUT': 'memory:'
    }
    clipped_layer = processing.run("native:clip", params, feedback=QgsProcessingFeedback())
    clpdlayer = clipped_layer['OUTPUT']

    layer_provider = clpdlayer.dataProvider()
    length_field = QgsField('length', QVariant.Double)
    bearing_field = QgsField('bearing', QVariant.Double)

    # Check if the 'length' field already exists (it shouldn't but just in case)
    if not any(field.name() == 'length' for field in clpdlayer.fields()):
        layer_provider.addAttributes([length_field])
        clpdlayer.updateFields()
    if not any(field.name() == 'bearing' for field in clpdlayer.fields()):
        layer_provider.addAttributes([bearing_field])
        clpdlayer.updateFields()

    # Calculate the length for each feature and update the 'length' field
    expression = QgsExpression('$length')
    bearing_expression = QgsExpression('degrees(azimuth(start_point($geometry), end_point($geometry)))')
    context = QgsExpressionContext()
    context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(clpdlayer))
    
    # Start editing the layer
    clpdlayer.startEditing()

    # Iterate through features and update the 'length' field
    for feature in clpdlayer.getFeatures():
        context.setFeature(feature)
        feature['length'] = expression.evaluate(context)
        feature['bearing'] = bearing_expression.evaluate(context)
        clpdlayer.updateFeature(feature)

    # Update the layer's attribute table to reflect the changes
    clpdlayer.commitChanges()
    clpdlayer.updateExtents()

    # shorthand names for faults - for output name
    
    cf_layer = QgsVectorLayer('LineString?crs=' + input_layer.crs().authid(), 'selected_features', 'memory')
    cf_provider = cf_layer.dataProvider()
    cf_provider.addAttributes(input_layer.fields())
    cf_layer.updateFields()
    
    for feature in input_layer.getFeatures():
        cf_provider.addFeature(feature)
    
    nshs = []
    for feature in cf_layer.getFeatures():
        fname = feature['name']
        nshs += [''.join([char for char in fname if char.isupper()])]
    
    
    n_sh = ''.join([char for char in N_fault if char.isupper()])
    s_sh = ''.join([char for char in S_fault if char.isupper()])
    
    if nshs.count(n_sh) != 1:
        n_sh = ''
        uppercase_found = False

        # Iterate through each character in the string
        for char in N_fault:
            if char.isupper():
                n_sh += char
                uppercase_found = True
            elif uppercase_found and char.islower():
                n_sh += char
                uppercase_found = False
    
    elif nshs.count(s_sh) != 1:
        s_sh = ''
        uppercase_found = False

        # Iterate through each character in the string
        for char in S_fault:
            if char.isupper():
                s_sh += char
                uppercase_found = True
            elif uppercase_found and char.islower():
                s_sh += char
                uppercase_found = False
            
    d_int = int(depth)

    from statistics import mean, stdev

    # Extract all length values from the 'length' field
    lengths = [f['length'] for f in clpdlayer.getFeatures()]
    bearings = [f['bearing'] for f in clpdlayer.getFeatures()]
    
    for i in range(len(bearings)):
        if bearings[i] >= 180:
            bearings[i] = 360 - bearings[i]

    # Calculate the mean and standard deviation
    mean_length = mean(lengths)
    stdev_length = stdev(lengths) if len(lengths) > 1 else 0  # Avoid stdev calculation for single value
    
    mean_bearing = mean(bearings)    
    
    # print(mean_bearing, mean_strikes)
    if not compatibility:
        if abs(mean_bearing - mean_strikes) < 20 and stdev(bearings) < 20:
            namevar = 'O'
            vnamevar = 'Overlap'
            overlap = mean_length
            over_std = stdev_length
        else:
            namevar = 'S'
            vnamevar = 'Separation'
            separation = mean_length
            sep_std = stdev_length
    else:
        if abs(mean_bearing - mean_strikes) < 30 and stdev(bearings) < 20: 
            namevar = 'O'
            vnamevar = 'Overlap'
            overlap = mean_length
            over_std = stdev_length
        else:
            namevar = 'S'
            vnamevar = 'Separation'
            separation = mean_length
            sep_std = stdev_length
    # Print the results
    
    print(mean_strikes, mean_bearing, stdev(bearings))
    print(f"{d_int}m_{n_sh}_{s_sh}_{namevar}")
    print(f"Mean Length for {vnamevar}: {mean_length}")
    print(f"Standard Deviation of Length for {vnamevar}: {stdev_length}")
    
    print("")
    
    # layer output
    clpdlayer.setName(f"{d_int}m_{n_sh}_{s_sh}_{namevar}")
    QgsProject.instance().addMapLayer(clpdlayer)
    
    itervar+=1

print("")
print("O/S: ",overlap/separation)

s_layer_provider = selected_features_layer.dataProvider()
length_field = QgsField('length', QVariant.Double)

# Check if the 'length' field already exists (it shouldn't but just in case)
if not any(field.name() == 'length' for field in selected_features_layer.fields()):
    s_layer_provider.addAttributes([length_field])
    clpdlayer.updateFields()

context = QgsExpressionContext()
context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(selected_features_layer))

# Start editing the layer
selected_features_layer.startEditing()
    
for feature in selected_features_layer.getFeatures():
    context.setFeature(feature)
    feature['length'] = expression.evaluate(context)
    selected_features_layer.updateFeature(feature)

selected_features_layer.commitChanges()
selected_features_layer.updateExtents()

polygons_layer.startEditing()

Tlengths = [f['length'] for f in selected_features_layer.getFeatures()]
print("TL = ",sum(Tlengths))

polys_layer_provider = polygons_layer.dataProvider()
stdS_field = QgsField('std_S', QVariant.Double)
stdO_field = QgsField('std_O', QVariant.Double)
avgS_field = QgsField('avg_S', QVariant.Double)
avgO_field = QgsField('avg_O', QVariant.Double)
O_S_field = QgsField('O_S', QVariant.Double)
TL_field = QgsField('TL', QVariant.Double)

polys_layer_provider.addAttributes([stdS_field,stdO_field,avgS_field,avgO_field,
                                    O_S_field, TL_field])
polygons_layer.updateFields() 
                                    
for feature in polygons_layer.getFeatures():
    # Create a new feature with the updated attributes
    new_feature = feature
    new_feature['std_S'] = sep_std
    new_feature['std_O'] = over_std
    new_feature['avg_S'] = separation
    new_feature['avg_O'] = overlap
    new_feature['O_S'] = overlap / separation if separation != 0 else None  # Avoid division by zero
    new_feature['TL'] = sum(Tlengths)
    
    # Update the feature in the layer
    polygons_layer.updateFeature(new_feature)

polygons_layer.commitChanges()

polygons_layer.setName(f"{d_int}m_{n_sh}_{s_sh}_poly")
QgsProject.instance().addMapLayer(polygons_layer) # debug