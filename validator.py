import json
import logging
from pydantic import BaseModel, field_validator, ValidationError as PydanticValidationError
from shapely.geometry import shape, Polygon, MultiPolygon
from jsonschema import validate, ValidationError as JsonSchemaValidationError

# Configuración básica del logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Esquema de validación de GeoJSON
geojson_schema = {
    "type": "object",
    "properties": {
        "type": {"type": "string"},
        "features": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string"},
                    "properties": {"type": "object"},
                    "geometry": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string"},
                            "coordinates": {"type": "array"}
                        },
                        "required": ["type", "coordinates"]
                    }
                },
                "required": ["type", "properties", "geometry"]
            }
        }
    },
    "required": ["type", "features"]
}

# Función para validar GeoJSON
def validate_geojson(geojson):
    try:
        if isinstance(geojson, str):
            geojson_dict = json.loads(geojson)
        else:
            geojson_dict = geojson
        
        validate(instance=geojson_dict, schema=geojson_schema)
        logger.info("GeoJSON es válido.")
        return geojson_dict
    except (json.JSONDecodeError, JsonSchemaValidationError) as e:
        logger.error(f"GeoJSON no es válido: {e}")
        raise ValueError(f"GeoJSON no es válido: {e}")

# Función para verificar la topología de los polígonos
def check_topology(geometry):
    if isinstance(geometry, (Polygon, MultiPolygon)):
        if not geometry.is_valid:
            logger.error(f"Geometría no válida: {geometry}")
            return False
        return True
    else:
        logger.error("Tipo de geometría no soportado para la validación.")
        return False

# Clase para la validación del input
class GeoJSONInput(BaseModel):
    geojson: str

    @field_validator('geojson')
    def validate_geojson_input(cls, value):
        try:
            # Intenta cargar el JSON para validar su formato
            geojson_data = json.loads(value)
            
            if not isinstance(geojson_data, dict) or 'type' not in geojson_data or geojson_data['type'] != 'FeatureCollection':
                raise ValueError('El GeoJSON debe ser de tipo FeatureCollection.')

            if 'features' not in geojson_data or not isinstance(geojson_data['features'], list):
                raise ValueError('El GeoJSON debe contener una lista de features.')

            # Validación del esquema GeoJSON
            validate_geojson(geojson_data)

            return value
        except json.JSONDecodeError:
            raise ValueError('El GeoJSON no es válido.')

    @classmethod
    def parse_geojson(cls, data):
        try:
            geojson_data = json.loads(data.geojson)
            return geojson_data
        except json.JSONDecodeError:
            raise ValueError('El GeoJSON no es válido.')
