from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from validator import GeoJSONInput, check_topology
from cruces import load_geojson_from_text, ensure_same_crs, calculate_bbox, query_wfs_layer, calculate_intersections, generate_map_image, generate_pdf, save_json, detect_overlaps
from datetime import datetime
import os
import json
import logging
from shapely.geometry import shape

# Configuración básica del logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

@app.post("/analyze/")
async def analyze_geojson(data: GeoJSONInput):
    try:
        logger.info("Recibido GeoJSON para análisis.")
        
        # Parsear el GeoJSON usando la clase de validador
        geojson_dict = GeoJSONInput.parse_geojson(data)
        
        valid_features = []
        for feature in geojson_dict["features"]:
            geometry = shape(feature["geometry"])
            if check_topology(geometry):
                valid_features.append(feature)

        valid_geojson_data = {
            "type": "FeatureCollection",
            "features": valid_features
        }

        geojson_text = json.dumps(valid_geojson_data)
        polygons_gdf = load_geojson_from_text(geojson_text)

        logger.info("Polígonos válidos cargados: %d", len(polygons_gdf))

        today = datetime.today().strftime('%Y-%m-%d')
        geojson_filename = "input_geojson"

        output_image = f"/tmp/mapa_{geojson_filename}_{today}.png"
        output_pdf = f"/tmp/reporte_{geojson_filename}_{today}.pdf"
        json_uso_suelo = f"/tmp/intersecciones_uso_suelo_{geojson_filename}_{today}.json"
        json_federales = f"/tmp/intersecciones_federales_{geojson_filename}_{today}.json"
        json_estatales = f"/tmp/intersecciones_estatales_{geojson_filename}_{today}.json"
        json_municipales = f"/tmp/intersecciones_municipales_{geojson_filename}_{today}.json"
        json_locales = f"/tmp/intersecciones_locales_{geojson_filename}_{today}.json"
        json_regionales = f"/tmp/intersecciones_regionales_{geojson_filename}_{today}.json"

        crs_target = 'EPSG:4326'
        polygons_gdf = ensure_same_crs(polygons_gdf, crs_target)
        bbox = calculate_bbox(polygons_gdf)

        wfs_url_uso_suelo = "https://app.semarnat.gob.mx/geoserver/DGPEE/wfs"
        layer_name_uso_suelo = "DGPEE:usuev250sVII"
        usos_suelo = query_wfs_layer(wfs_url_uso_suelo, layer_name_uso_suelo, bbox, crs_target)

        wfs_url_federales = "https://app.semarnat.gob.mx/geoserver/DGPEE_Biodiversidad_Ecosistemas/wfs"
        layer_name_federales = "DGPEE_Biodiversidad_Ecosistemas:anp186_itrf08_19012023"
        anp_federales = query_wfs_layer(wfs_url_federales, layer_name_federales, bbox, crs_target)

        wfs_url_estatales = "https://app.semarnat.gob.mx/geoserver/DGPEE_Biodiversidad_Ecosistemas/wfs"
        layer_name_estatales = "DGPEE_Biodiversidad_Ecosistemas:anpest15gw"
        anp_estatales = query_wfs_layer(wfs_url_estatales, layer_name_estatales, bbox, crs_target)

        wfs_url_municipales = "https://app.semarnat.gob.mx/geoserver/DGPEE_Biodiversidad_Ecosistemas/wfs"
        layer_name_municipales = "DGPEE_Biodiversidad_Ecosistemas:anpest15gw"
        anp_municipales = query_wfs_layer(wfs_url_municipales, layer_name_municipales, bbox, crs_target)

        wfs_url_locales = "https://app.semarnat.gob.mx/geoserver/DGPEE_Ordenamientos/wfs"
        layer_name_locales = "DGPEE_Ordenamientos:LOCALES_107_221231"
        locales = query_wfs_layer(wfs_url_locales, layer_name_locales, bbox, crs_target)

        wfs_url_regionales = "https://app.semarnat.gob.mx/geoserver/DGPEE_Ordenamientos/wfs"
        layer_name_regionales = "DGPEE_Ordenamientos:REGIONALES_53220930"
        regionales = query_wfs_layer(wfs_url_regionales, layer_name_regionales, bbox, crs_target)

        usos_suelo = ensure_same_crs(usos_suelo, crs_target)
        anp_federales = ensure_same_crs(anp_federales, crs_target)
        anp_estatales = ensure_same_crs(anp_estatales, crs_target)
        anp_municipales = ensure_same_crs(anp_municipales, crs_target)
        locales = ensure_same_crs(locales, crs_target)
        regionales = ensure_same_crs(regionales, crs_target)

        intersections_uso_suelo = calculate_intersections(polygons_gdf, usos_suelo, 'Usos de Suelo Serie VII', ['tip_veg','des_veg'])
        intersections_federales = calculate_intersections(polygons_gdf, anp_federales, 'Áreas Naturales Protegidas Federales', ['id_anp', 'nombre', 'cat_manejo', 'superficie', 'region'])
        intersections_estatales = calculate_intersections(polygons_gdf, anp_estatales, 'Áreas Naturales Protegidas Estatales', ['nombre', 'entidad', 'mun_dec', 'area', 'enlace_dec'])
        intersections_municipales = calculate_intersections(polygons_gdf, anp_municipales, 'Áreas Naturales Protegidas Municipales', ['nombre', 'entidad', 'mun_dec', 'area', 'enlace_dec'])
        intersections_locales = calculate_intersections(polygons_gdf, locales, 'Ordenamientos Locales', ['nom_mun', 'ordenamine', 'situacion', 'decreto', 'concenio'], tipo_ordenamiento="Ordenamiento Local")
        intersections_regionales = calculate_intersections(polygons_gdf, regionales, 'Ordenamientos Regionales', ['nom_ent', 'situacion', 'ordenamien', 'f_decreto'], tipo_ordenamiento="Ordenamiento Regional")

        overlaps = detect_overlaps(polygons_gdf)

        save_json(intersections_uso_suelo, json_uso_suelo)
        save_json(intersections_federales, json_federales)
        save_json(intersections_estatales, json_estatales)
        save_json(intersections_municipales, json_municipales)
        save_json(intersections_locales, json_locales)
        save_json(intersections_regionales, json_regionales)

        generate_map_image(polygons_gdf, output_image)
        generate_pdf(polygons_gdf, output_pdf, output_image, intersections_uso_suelo, intersections_federales, intersections_estatales, intersections_municipales, intersections_locales, intersections_regionales, overlaps)

        return {
            "map_image": output_image,
            "report_pdf": output_pdf,
            "intersections_uso_suelo": json_uso_suelo,
            "intersections_federales": json_federales,
            "intersections_estatales": json_estatales,
            "intersections_municipales": json_municipales,
            "intersections_locales": json_locales,
            "intersections_regionales": json_regionales
        }
    except Exception as e:
        logger.error("Error al analizar el GeoJSON: %s", e)
        raise HTTPException(status_code=400, detail=f"Error al analizar el GeoJSON: {e}")

@app.get("/download/{file_path:path}")
async def download_file(file_path: str):
    file_location = os.path.join("/tmp", file_path)
    
    if not os.path.exists(file_location):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(file_location)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
