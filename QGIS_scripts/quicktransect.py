from qgis.core import QgsProject, QgsProcessingFeatureSourceDefinition, QgsProcessing

# Define input parameters
layer_name = 'ca_rect'
transect_length = 100000  # 100 km in meters

# Retrieve the input layer
layer = QgsProject.instance().mapLayersByName(layer_name)[0]

# Get selected features
selected_features = layer.selectedFeatures()
if not selected_features:
    print("No feature selected.")
else:
    # Use the first selected feature
    feature = selected_features[0]
    geom = feature.geometry()

    # Set up parameters for the processing algorithm
    params = {
        'INPUT': QgsProcessingFeatureSourceDefinition(layer.id(), True),
        'LENGTH': 100000,
        'ANGLE': 90,  # Default angle, adjust as needed,
        'SIDE':2,
        'OUTPUT': 'memory:'  # Output to a temporary memory layer
    }

    # Run the 'native:transect' algorithm
    result = processing.run('native:transect', params)

    # Get the output layer
    transect_layer = result['OUTPUT']
    
    # Add the transect layer to the project
    QgsProject.instance().addMapLayer(transect_layer)

    print("Transect layer created")