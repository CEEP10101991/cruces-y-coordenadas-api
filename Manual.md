
# Manual de Usuario para la API con FastAPI

## Configuración del Entorno

1. **Instalar Conda**: Asegúrate de tener Conda instalado en tu sistema. Puedes descargarlo desde [aquí](https://docs.conda.io/projects/conda/en/latest/user-guide/install/index.html).

2. **Crear un entorno virtual**:
    ```bash
    conda create --name myenv python=3.8
    conda activate myenv
    ```

3. **Instalar las dependencias**:
    ```bash
    pip install -r requirements.txt
    ```

## Ejecución de la API

1. **Ubica los archivos**: Asegúrate de que los archivos `main.py`, `cruces.py`, y `validator.py` estén en el mismo directorio.

2. **Iniciar la API**:
    ```bash
    uvicorn main:app --reload
    ```

3. **Acceder a la API**: Una vez que la API esté en funcionamiento, puedes acceder a la documentación interactiva en `http://127.0.0.1:8000/docs`.

## Uso de la API

1. **Endpoints disponibles**: Los endpoints de tu API estarán documentados automáticamente en la interfaz interactiva de Swagger en `http://127.0.0.1:8000/docs`.

2. **Ejemplo de consumo de un endpoint**:
    ```python
    import requests

    response = requests.get("http://127.0.0.1:8000/tu_endpoint")
    print(response.json())
    ```
