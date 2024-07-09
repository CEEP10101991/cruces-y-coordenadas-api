# cruces-y-coordenadas-api

# API con FastAPI

Este proyecto implementa una API utilizando FastAPI. La API permite validar y procesar datos GeoJSON relacionados con predios y polígonos.

## Archivos

### main.py
Este archivo contiene la configuración principal de la API. Define los endpoints y las rutas para interactuar con los datos GeoJSON.

### cruces.py
Este archivo contiene la lógica para manejar las operaciones de cruce y validación de los polígonos. Incluye funciones para procesar y verificar las relaciones espaciales entre diferentes polígonos.

### validator.py
Este archivo incluye funciones de validación para asegurarse de que los datos GeoJSON cumplan con los requisitos específicos del proyecto. Verifica la estructura y los datos contenidos en los GeoJSON.

## Ejecución de la API

1. **Instalar Conda**: [Instrucciones de instalación](https://docs.conda.io/projects/conda/en/latest/user-guide/install/index.html).
2. **Crear un entorno virtual**:
    ```bash
    conda create --name myenv python=3.8
    conda activate myenv
    ```
3. **Instalar las dependencias**:
    ```bash
    pip install -r requirements.txt
    ```
4. **Iniciar la API**:
    ```bash
    uvicorn main:app --reload
    ```
5. **Acceder a la API**: `http://127.0.0.1:8000/docs` para la documentación interactiva.

## Consumo de la API

Ejemplo de uso de un endpoint:
```python
import requests

response = requests.get("http://127.0.0.1:8000/tu_endpoint")
print(response.json())
```

## Formato JSON soportado

La API consume datos en formato GeoJSON con la siguiente estructura:
```json
{
  "geojson": "{"type":"FeatureCollection","features":[{"type":"Feature","properties":{"predio_id":"las cruces"},"geometry":{"type":"Polygon","coordinates":[[[-99.87100581060821,16.891530904567873],[-99.87100581060821,16.88722343026572],[-99.86307166743902,16.88722343026572],[-99.86307166743902,16.891530904567873],[-99.87100581060821,16.891530904567873]]]}}, ...]}"
}
```
Cada `Feature` en el `FeatureCollection` debe tener un `predio_id` que identifique a qué predio pertenece. Todos los polígonos dentro de un mismo predio deben compartir este `predio_id`.
