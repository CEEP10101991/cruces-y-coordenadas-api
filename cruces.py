import geopandas as gpd
import json
from shapely.geometry import shape, Polygon, MultiPolygon
from owslib.wfs import WebFeatureService
import matplotlib.pyplot as plt
from fpdf import FPDF
import os
from datetime import datetime

# Función para realizar la consulta WFS y convertir a GeoDataFrame
def query_wfs_layer(wfs_url, layer_name, bbox, crs):
    wfs = WebFeatureService(url=wfs_url, version='1.1.0')
    response = wfs.getfeature(
        typename=layer_name,
        bbox=bbox,
        outputFormat='application/json'
    )
    gdf = gpd.read_file(response)
    print(f"Descargado {len(gdf)} características de {layer_name}")
    gdf.crs = crs  # Establece el CRS a EPSG:4326
    return gdf

# Función para calcular el bounding box de los polígonos
def calculate_bbox(polygons_gdf):
    minx, miny, maxx, maxy = polygons_gdf.total_bounds
    return (minx, miny, maxx, maxy)

# Función para cargar GeoJSON desde un texto y soportar múltiples tipos de geometrías
def load_geojson_from_text(geojson_text):
    try:
        geojson_dict = json.loads(geojson_text)
        geometries = []
        predio_ids = []
        subpoligono_ids = []

        for feature in geojson_dict["features"]:
            geom = shape(feature["geometry"])
            predio_id = feature["properties"].get("predio_id", "Desconocido")
            subpoligono_id = feature["properties"].get("poligono", None)
            
            if subpoligono_id is None:
                subpoligono_id = f"{predio_id}_subpoligono_{len(geometries)+1}"
                feature["properties"]["poligono"] = subpoligono_id

            if isinstance(geom, (Polygon, MultiPolygon)):
                geometries.append(geom)
                predio_ids.append(predio_id)
                subpoligono_ids.append(subpoligono_id)
            else:
                geometries.extend([g for g in geom if isinstance(g, (Polygon, MultiPolygon))])
                predio_ids.append(predio_id)
                subpoligono_ids.append(subpoligono_id)

        gdf = gpd.GeoDataFrame({"geometry": geometries, "predio_id": predio_ids, "subpoligono_id": subpoligono_ids})
        gdf.crs = 'EPSG:4326'
        
        if 'id' not in gdf.columns:
            gdf['id'] = range(1, len(gdf) + 1)
        
        return gdf
    except json.JSONDecodeError as e:
        print(f"Error al decodificar JSON: {e}")
        raise ValueError("El texto GeoJSON no es válido")

# Función para asegurar que todas las capas tienen el mismo CRS
def ensure_same_crs(gdf, crs):
    if gdf.crs is None or gdf.crs.to_string() != crs:
        gdf = gdf.to_crs(crs)
    return gdf

# Función para realizar el cruce espacial y calcular el área de intersección
def calculate_intersections(polygons_gdf, layer, layer_name, fields, tipo_ordenamiento=None):
    results = []
    print(f"Procesando intersecciones con la capa: {layer_name}")
    for poly_index, polygon in polygons_gdf.iterrows():
        poly_geom = polygon['geometry']
        for feature_index, feature in layer.iterrows():
            feature_geom = feature['geometry']
            if poly_geom.intersects(feature_geom):
                intersection = poly_geom.intersection(feature_geom)
                if not intersection.is_empty:
                    area = intersection.area
                    # Estimación en metros cuadrados
                    area_m2 = area * 12321000000  # Estimación basada en un grado cuadrado en el ecuador
                    record = {
                        'Polygon_ID': polygon['id'],
                        'Predio_ID': polygon['predio_id'],
                        'Subpoligono_ID': polygon['subpoligono_id'],
                        'Layer': layer_name,
                        'Feature_ID': feature['id'],
                        'Intersection_Area_Degrees': area,
                        'Intersection_Area_M2': f"{area_m2:.2f} m² (estimado)"
                    }
                    if tipo_ordenamiento:
                        record['Tipo'] = tipo_ordenamiento
                    for field in fields:
                        record[field] = feature.get(field, 'Desconocido')
                    results.append(record)
                    print(f"Intersección encontrada: Polígono ID {polygon['id']} con {layer_name}, Área: {area:.6f} grados cuadrados ≈ {area_m2:.2f} m² (estimado)")
    return results

# Función para detectar superposiciones
def detect_overlaps(polygons_gdf):
    overlaps = []
    for i, poly1 in polygons_gdf.iterrows():
        for j, poly2 in polygons_gdf.iterrows():
            if i >= j:
                continue
            if poly1['geometry'].intersects(poly2['geometry']):
                intersection = poly1['geometry'].intersection(poly2['geometry'])
                if not intersection.is_empty:
                    area = intersection.area
                    overlaps.append({
                        'Polygon1_ID': poly1['id'],
                        'Polygon1_Predio_ID': poly1['predio_id'],
                        'Polygon1_Subpoligono_ID': poly1['subpoligono_id'],
                        'Polygon2_ID': poly2['id'],
                        'Polygon2_Predio_ID': poly2['predio_id'],
                        'Polygon2_Subpoligono_ID': poly2['subpoligono_id'],
                        'Overlap_Area_Degrees': area,
                        'Overlap_Area_M2': f"{area * 12321000000:.2f} m² (estimado)"
                    })
    return overlaps

# Función para guardar datos en JSON
def save_json(data, filename):
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)

# Función para sanitizar el texto
def sanitize_text(text):
    return text.encode('latin-1', 'replace').decode('latin-1')

# Función para generar y guardar la imagen del mapa
def generate_map_image(polygons_gdf, output_image):
    plt.figure(figsize=(10, 8))
    ax = polygons_gdf.plot(column='id', cmap='tab20', legend=True)
    ax.set_title('Mapa de Polígonos')
    plt.axis('equal')
    plt.savefig(output_image)
    plt.close()

# Clase personalizada para el PDF
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'Reporte de Polígonos GeoJSON y Cruce Espacial', 0, 1, 'C')

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

# Función para generar el PDF
def generate_pdf(polygons_gdf, output_pdf, output_image, intersections_uso_suelo, intersections_federales, intersections_estatales, intersections_municipales, intersections_locales, intersections_regionales, overlaps):
    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=10)
    pdf.set_font("Arial", size=10)

    # Verificar si el archivo de imagen existe antes de agregarlo
    if os.path.exists(output_image):
        pdf.add_page()
        pdf.image(output_image, x=10, y=20, w=180)
        pdf.add_page()
    else:
        print(f"Error: El archivo de imagen '{output_image}' no se encontró.")

    predios = polygons_gdf.groupby('predio_id')

    for predio_id, predio_df in predios:
        pdf.add_page()
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, f"Predio: {predio_id}", 0, 1, 'C')
        pdf.ln(5)

        pdf.set_font("Arial", 'B', 10)
        pdf.cell(0, 10, "Coordenadas del predio:", 0, 1, 'C')
        pdf.set_font("Arial", size=8)

        predio_geom = predio_df.unary_union
        if isinstance(predio_geom, Polygon):
            for coord in predio_geom.exterior.coords:
                coord_text = f"{coord}"
                cell_height = 5
                pdf.multi_cell(0, cell_height, sanitize_text(coord_text), border=1)
        elif isinstance(predio_geom, MultiPolygon):
            for poly in predio_geom.geoms:
                pdf.ln(5)
                pdf.set_font("Arial", 'I', 10)
                pdf.cell(0, 10, "Sub-polígono:", ln=True)
                pdf.set_font("Arial", size=8)
                for coord in poly.exterior.coords:
                    coord_text = f"{coord}"
                    cell_height = 5
                    pdf.multi_cell(0, cell_height, sanitize_text(coord_text), border=1)

        for i, polygon in predio_df.iterrows():
            pdf.ln(10)
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(0, 10, f"Subpolígono {polygon['subpoligono_id']}", 0, 1, 'C')
            pdf.ln(5)

            pdf.set_font("Arial", size=10)
            pdf.cell(50, 10, "Área (grados cuadrados):", border=1)
            pdf.cell(0, 10, f"{polygon['geometry'].area:.6f}", border=1, ln=True)
            pdf.cell(50, 10, "Área estimada (m²):", border=1)
            pdf.cell(0, 10, f"{polygon['geometry'].area * 12321000000:.2f} m² (estimado)", border=1, ln=True)
            pdf.cell(50, 10, "Perímetro:", border=1)
            pdf.cell(0, 10, f"{polygon['geometry'].length:.2f} unidades", border=1, ln=True)

            pdf.ln(5)
            pdf.set_font("Arial", 'B', 10)
            pdf.cell(0, 10, "Coordenadas del subpolígono:", border=1, ln=True, align='C')
            pdf.set_font("Arial", size=8)

            geometry = polygon['geometry']
            if isinstance(geometry, Polygon):
                for coord in geometry.exterior.coords:
                    coord_text = f"{coord}"
                    cell_height = 5
                    pdf.multi_cell(0, cell_height, sanitize_text(coord_text), border=1)
            elif isinstance(geometry, MultiPolygon):
                for poly in geometry.geoms:
                    pdf.ln(5)
                    pdf.set_font("Arial", 'I', 10)
                    pdf.cell(0, 10, "Sub-polígono:", ln=True)
                    pdf.set_font("Arial", size=8)
                    for coord in poly.exterior.coords:
                        coord_text = f"{coord}"
                        cell_height = 5
                        pdf.multi_cell(0, cell_height, sanitize_text(coord_text), border=1)

    # Detalles de las intersecciones con Usos de Suelo
    if intersections_uso_suelo:
        pdf.add_page()
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, "Intersecciones con Usos de Suelo", 0, 1, 'C')
        pdf.ln(5)

        pdf.set_font("Arial", size=10)
        for intersection in intersections_uso_suelo:
            if pdf.get_y() > 260:
                pdf.add_page()
            pdf.cell(0, 10, f"Polígono ID: {intersection['Polygon_ID']} (Predio: {intersection['Predio_ID']}, Subpolígono: {intersection['Subpoligono_ID']})", ln=True)
            pdf.cell(0, 10, f"ID de Característica: {intersection['Feature_ID']}", ln=True)
            pdf.cell(0, 10, f"Área de Intersección (grados cuadrados): {intersection['Intersection_Area_Degrees']:.6f}", ln=True)
            pdf.cell(0, 10, f"Área de Intersección (m²): {intersection['Intersection_Area_M2']}", ln=True)
            pdf.cell(0, 10, f"Tipo de Vegetación: {intersection.get('tip_veg', 'N/A')}", ln=True)
            pdf.cell(0, 10, f"Descripción de Vegetación: {intersection.get('des_veg', 'N/A')}", ln=True)
            pdf.ln(5)

    # Detalles de las intersecciones con ANP Federales
    if intersections_federales:
        pdf.add_page()
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, "Intersecciones con ANP Federales", 0, 1, 'C')
        pdf.ln(5)

        pdf.set_font("Arial", size=10)
        for intersection in intersections_federales:
            if pdf.get_y() > 260:
                pdf.add_page()
            pdf.cell(0, 10, f"Polígono ID: {intersection['Polygon_ID']} (Predio: {intersection['Predio_ID']}, Subpolígono: {intersection['Subpoligono_ID']})", ln=True)
            pdf.cell(0, 10, f"ID de Característica: {intersection['Feature_ID']}", ln=True)
            pdf.cell(0, 10, f"Área de Intersección (grados cuadrados): {intersection['Intersection_Area_Degrees']:.6f}", ln=True)
            pdf.cell(0, 10, f"Área de Intersección (m²): {intersection['Intersection_Area_M2']}", ln=True)
            pdf.cell(0, 10, f"ID_ANP: {intersection.get('id_anp', 'N/A')}", ln=True)
            pdf.cell(0, 10, f"Nombre del ANP: {intersection.get('nombre', 'N/A')}", ln=True)
            pdf.cell(0, 10, f"Categoría de Manejo: {intersection.get('cat_manejo', 'N/A')}", ln=True)
            pdf.cell(0, 10, f"Superficie del ANP: {intersection.get('superficie', 'N/A')}", ln=True)
            pdf.cell(0, 10, f"Región: {intersection.get('region', 'N/A')}", ln=True)
            pdf.ln(5)

    # Detalles de las intersecciones con ANP Estatales
    if intersections_estatales:
        pdf.add_page()
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, "Intersecciones con ANP Estatales", 0, 1, 'C')
        pdf.ln(5)

        pdf.set_font("Arial", size=10)
        for intersection in intersections_estatales:
            if pdf.get_y() > 260:
                pdf.add_page()
            pdf.cell(0, 10, f"Polígono ID: {intersection['Polygon_ID']} (Predio: {intersection['Predio_ID']}, Subpolígono: {intersection['Subpoligono_ID']})", ln=True)
            pdf.cell(0, 10, f"ID de Característica: {intersection['Feature_ID']}", ln=True)
            pdf.cell(0, 10, f"Área de Intersección (grados cuadrados): {intersection['Intersection_Area_Degrees']:.6f}", ln=True)
            pdf.cell(0, 10, f"Área de Intersección (m²): {intersection['Intersection_Area_M2']}", ln=True)
            pdf.cell(0, 10, f"Nombre del ANP: {intersection.get('nombre', 'N/A')}", ln=True)
            pdf.cell(0, 10, f"Entidad: {intersection.get('entidad', 'N/A')}", ln=True)
            pdf.cell(0, 10, f"Municipio: {intersection.get('mun_dec', 'N/A')}", ln=True)
            pdf.cell(0, 10, f"Área: {intersection.get('area', 'N/A')}", ln=True)
            pdf.cell(0, 10, f"Enlace: {intersection.get('enlace_dec', 'N/A')}", ln=True)
            pdf.ln(5)

    # Detalles de las intersecciones con ANP Municipales
    if intersections_municipales:
        pdf.add_page()
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, "Intersecciones con ANP Municipales", 0, 1, 'C')
        pdf.ln(5)

        pdf.set_font("Arial", size=10)
        for intersection in intersections_municipales:
            if pdf.get_y() > 260:
                pdf.add_page()
            pdf.cell(0, 10, f"Polígono ID: {intersection['Polygon_ID']} (Predio: {intersection['Predio_ID']}, Subpolígono: {intersection['Subpoligono_ID']})", ln=True)
            pdf.cell(0, 10, f"ID de Característica: {intersection['Feature_ID']}", ln=True)
            pdf.cell(0, 10, f"Área de Intersección (grados cuadrados): {intersection['Intersection_Area_Degrees']:.6f}", ln=True)
            pdf.cell(0, 10, f"Área de Intersección (m²): {intersection['Intersection_Area_M2']}", ln=True)
            pdf.cell(0, 10, f"Nombre del ANP: {intersection.get('nombre', 'N/A')}", ln=True)
            pdf.cell(0, 10, f"Entidad: {intersection.get('entidad', 'N/A')}", ln=True)
            pdf.cell(0, 10, f"Municipio: {intersection.get('mun_dec', 'N/A')}", ln=True)
            pdf.cell(0, 10, f"Área: {intersection.get('area', 'N/A')}", ln=True)
            pdf.cell(0, 10, f"Enlace: {intersection.get('enlace_dec', 'N/A')}", ln=True)
            pdf.ln(5)

    # Detalles de las intersecciones con Ordenamientos Locales
    if intersections_locales:
        pdf.add_page()
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, "Intersecciones con Ordenamientos Locales", 0, 1, 'C')
        pdf.ln(5)

        pdf.set_font("Arial", size=10)
        for intersection in intersections_locales:
            if pdf.get_y() > 260:
                pdf.add_page()
            pdf.cell(0, 10, f"Polígono ID: {intersection['Polygon_ID']} (Predio: {intersection['Predio_ID']}, Subpolígono: {intersection['Subpoligono_ID']})", ln=True)
            pdf.cell(0, 10, f"ID de Característica: {intersection['Feature_ID']}", ln=True)
            pdf.cell(0, 10, f"Área de Intersección (grados cuadrados): {intersection['Intersection_Area_Degrees']:.6f}", ln=True)
            pdf.cell(0, 10, f"Área de Intersección (m²): {intersection['Intersection_Area_M2']}", ln=True)
            pdf.cell(0, 10, f"Nombre del Municipio: {intersection.get('nom_mun', 'N/A')}", ln=True)
            pdf.cell(0, 10, f"Ordenamiento: {intersection.get('ordenamine', 'N/A')}", ln=True)
            pdf.cell(0, 10, f"Situación: {intersection.get('situacion', 'N/A')}", ln=True)
            pdf.cell(0, 10, f"Decreto: {intersection.get('decreto', 'N/A')}", ln=True)
            pdf.cell(0, 10, f"Convenio: {intersection.get('concenio', 'N/A')}", ln=True)
            pdf.ln(5)

    # Detalles de las intersecciones con Ordenamientos Regionales
    if intersections_regionales:
        pdf.add_page()
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, "Intersecciones con Ordenamientos Regionales", 0, 1, 'C')
        pdf.ln(5)

        pdf.set_font("Arial", size=10)
        for intersection in intersections_regionales:
            if pdf.get_y() > 260:
                pdf.add_page()
            pdf.cell(0, 10, f"Polígono ID: {intersection['Polygon_ID']} (Predio: {intersection['Predio_ID']}, Subpolígono: {intersection['Subpoligono_ID']})", ln=True)
            pdf.cell(0, 10, f"ID de Característica: {intersection['Feature_ID']}", ln=True)
            pdf.cell(0, 10, f"Área de Intersección (grados cuadrados): {intersection['Intersection_Area_Degrees']:.6f}", ln=True)
            pdf.cell(0, 10, f"Área de Intersección (m²): {intersection['Intersection_Area_M2']}", ln=True)
            pdf.cell(0, 10, f"Nombre de la Entidad: {intersection.get('nom_ent', 'N/A')}", ln=True)
            pdf.cell(0, 10, f"Situación: {intersection.get('situacion', 'N/A')}", ln=True)
            pdf.cell(0, 10, f"Ordenamiento: {intersection.get('ordenamien', 'N/A')}", ln=True)
            pdf.cell(0, 10, f"Fecha del Decreto: {intersection.get('f_decreto', 'N/A')}", ln=True)
            pdf.ln(5)

    # Detalles de las superposiciones
    if overlaps:
        pdf.add_page()
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, "Superposiciones entre Polígonos", 0, 1, 'C')
        pdf.ln(5)

        pdf.set_font("Arial", size=10)
        for overlap in overlaps:
            if pdf.get_y() > 260:
                pdf.add_page()
            pdf.cell(0, 10, f"Polígono 1 ID: {overlap['Polygon1_ID']} (Predio: {overlap['Polygon1_Predio_ID']}, Subpolígono: {overlap['Polygon1_Subpoligono_ID']})", ln=True)
            pdf.cell(0, 10, f"Polígono 2 ID: {overlap['Polygon2_ID']} (Predio: {overlap['Polygon2_Predio_ID']}, Subpolígono: {overlap['Polygon2_Subpoligono_ID']})", ln=True)
            pdf.cell(0, 10, f"Área de Superposición (grados cuadrados): {overlap['Overlap_Area_Degrees']:.6f}", ln=True)
            pdf.cell(0, 10, f"Área de Superposición (m²): {overlap['Overlap_Area_M2']}", ln=True)
            pdf.ln(5)

    pdf.output(output_pdf)
