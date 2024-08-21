from qgis.core import QgsProject, QgsVectorLayer, QgsFields, QgsField, QgsFeature, QgsGeometry, QgsPointXY
from qgis.PyQt.QtCore import QVariant

# Define the CRS and layer properties
crs = 'EPSG:32633'
layer_name = 'poly'

# Create a new vector layer
fields = QgsFields()
fields.append(QgsField('ID', QVariant.Int))

# Create the polygon layer with the defined CRS
layer = QgsVectorLayer(f'Polygon?crs={crs}', layer_name, 'memory')
layer.updateFields()

# Start editing the layer
layer.startEditing()

# Add the layer to the project
QgsProject.instance().addMapLayer(layer)

# Select the layer in the layer tree and open it in editing mode
iface.layerTreeView().setCurrentLayer(layer)
iface.actionToggleEditing().trigger()