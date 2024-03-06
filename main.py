# Importar bibliotecas de Python
import pandas as pd
from bs4 import BeautifulSoup 
import requests
from datetime import datetime

import openpyxl

from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer
from nltk.probability import FreqDist

# Función google_Noticias que se conecta a la pagina de google noticias y extrae los datos de Titulo, Fuente y fecha de cada noticia
# y al final crea un dataframe de las noticias con respecto a la niñez.

def google_noticias(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Extraer título de la noticia
    titulo_noticia = [h.text for h in soup.find_all('a', class_='JtKRv')]
    
    # Extraer fuente de la noticia
    fuente_noticia = [div.text for div in soup.find_all('div', class_='vr1PYe')]
    
    # Extraer fecha de la noticia
    fecha_noticia = [time['datetime'] for time in soup.find_all('time', class_='hvbAAd')]
    
    # Crear DataFrame
    df_noticias = pd.DataFrame({
        'titulo': titulo_noticia,
        'fuente': fuente_noticia,
        'fecha': pd.to_datetime(fecha_noticia),
        'fecha_consulta': datetime.now()
    })
    
    return df_noticias
# URLs de noticias en google noticias.

url_niño = "https://news.google.com/search?q=ni%C3%B1o&hl=es-419&gl=CO&ceid=CO%3Aes-419"
url_niña = "https://news.google.com/search?q=ni%C3%B1a&hl=es-419&gl=CO&ceid=CO%3Aes-419"
url_adolescente = "https://news.google.com/search?q=adolescente&hl=es-419&gl=CO&ceid=CO%3Aes-419"
url_bebe = "https://news.google.com/search?q=bebe&hl=es-419&gl=CO&ceid=CO%3Aes-419"
url_menor_edad = "https://news.google.com/search?q=menor%20de%20edad&hl=es-419&gl=CO&ceid=CO%3Aes-419"

# Ejecutar la función google_noticias para cada url y extraer los datos.

noticias_niño = google_noticias(url_niño)
noticias_niña = google_noticias(url_niña)
noticias_adolescente = google_noticias(url_adolescente)
noticias_bebe = google_noticias(url_bebe)
noticias_menor_edad = google_noticias(url_menor_edad)

# Unir los resultados en un solo DataFrame
noticias_colombia = pd.concat([noticias_niño, noticias_niña, noticias_adolescente, noticias_bebe, noticias_menor_edad], ignore_index=True)
#Creando variable Ciudad
# Se crea un vector con las ciudades de colombia. para hacer un analisis con las ciudades mencionadas en titulos de las noticias. (No todas las noticias en su titulo mencionan ciudad)

ciudades = ["Leticia", "Medellín", "Arauca", "Barranquilla", "Cartagena", "Tunja", "Manizales", "Florencia", "Yopal", 
            "Popayán", "Valledupar", "Quibdó", "Montería", "Bogotá", "Bogota", "Inírida", "San José del Guaviare", 
            "Neiva", "Riohacha", "Santa Marta", "Villavicencio", "Pasto", "Cúcuta", "Mocoa", "Armenia", "Pereira", 
            "San Andrés", "Bucaramanga", "Sincelejo", "Ibagué", "Cali", "Mitú", "Puerto Carreño"]

# Función para asignar una nueva columna llamada ciudad donde itera y agrega un campo con el nombre de la ciudad basándose en el título
def asignar_ciudad(titulo):
    for ciudad in ciudades:
        if ciudad.lower() in titulo.lower():
            return ciudad
    return None

# Creando la columna "ciudad" con la funcion anterior en la base de datos noticias_colombia
noticias_colombia['ciudad'] = noticias_colombia['titulo'].apply(asignar_ciudad)
## Filtrando ciudad de medellin, haciendo pruebas
noticias_colombia[noticias_colombia['ciudad'] == 'Medellín']

#Agregando variable Departamento
# Se crea un vector con los departamentos de colombia. para hacer un analisis con los departamentos mencionadas en titulos de las noticias. (No todas las noticias en su titulo mencionan un departamento)
departamentos = ["Amazonas", "Antioquia", "Arauca", "Atlántico", "Bolívar", "Boyacá", "Caldas", "Caquetá", "Casanare",
                 "Cauca", "Cesar", "Chocó", "Córdoba", "Cundinamarca", "Guainía", "Guaviare", "Huila", "La Guajira",
                 "Magdalena", "Meta", "Nariño", "Norte de Santander", "Putumayo", "Quindío", "Risaralda", 
                 "San Andrés y Providencia", "Santander", "Sucre", "Tolima", "Valle del Cauca", "Vaupés", "Vichada"]

# Función para asignar una nueva columna llamada departamento donde itera y agrega un campo con el nombre del departamento basándose en el título
def asignar_departamento(titulo):
    for departamento in departamentos:
        if departamento.lower() in titulo.lower():
            return departamento
    return None

# Creando la columna "departamento" con la funcion anterior en la base de datos noticias_colombia
noticias_colombia['departamento'] = noticias_colombia['titulo'].apply(asignar_departamento)
#Paso 5: Agregando la variable "maltrato" en Python
# Agregar una variable cuando contenga la palabra "maltrato" en el título, con 0 y 1
noticias_colombia['maltrato'] = noticias_colombia['titulo'].str.contains('maltrato', case=False).astype(int)

#Paso 6: Agregando las columnas de año, mes, día en Python
# Agregando columnas de año, mes, día
noticias_colombia['Año'] = noticias_colombia['fecha'].dt.year
noticias_colombia['Mes'] = noticias_colombia['fecha'].dt.month
noticias_colombia['DiaSemana'] = noticias_colombia['fecha'].dt.day_name()
noticias_colombia['DiaNumero'] = noticias_colombia['fecha'].dt.day

#eliminando columnas fecha y fecha_consulta#   luego debo eliminar este fragmento ya que la base de dats consolidada ya vendra sin estas columnas

noticias_colombia = noticias_colombia.drop(['fecha', 'fecha_consulta'], axis=1)
#Paso 7: Cargando base de datos guardada y uniendo datos nuevos en Python
# Cargando base de datos guardada
#noticias_colombia = pd.read_excel("Data/consolidado_noticias.xlsx")
# Cargando base de datos guardada
data_existente = pd.read_excel("Data/consolidado_noticias.xlsx")

# Unir base de datos guardada con datos nuevos
noticias_colombia1 = pd.concat([data_existente, noticias_colombia], ignore_index=True)

# Eliminar duplicados y guardar el nuevo consolidado
noticias_colombia = noticias_colombia1.drop_duplicates(subset=['titulo'])



# Eliminando las noticias del FENOMENO DEL NIÑO (SEQUÍA), ya que me trae estas noticias porque tiene la palabra NIÑO
# Filtrar por el texto en la columna 'titulo'
filtro_no_fenomeno = (~noticias_colombia['titulo'].str.contains('fenómeno de El Niño', case=False) &
                      ~noticias_colombia['titulo'].str.contains('fenómeno del Niño', case=False))




# Reindexar la serie booleana filtro_no_fenomeno para que coincida con el índice del DataFrame noticias_colombia
filtro_no_fenomeno = filtro_no_fenomeno.reindex(noticias_colombia.index)
# Aplicar el filtro al DataFrame para que no aparezca fenómeno del niño
noticias_colombia = noticias_colombia[filtro_no_fenomeno]



filtro_no_pais = (~noticias_colombia['titulo'].str.contains('argentina', case=False) &
                  ~noticias_colombia['titulo'].str.contains('mexico', case=False) &
                  ~noticias_colombia['titulo'].str.contains('peru', case=False) &
                  ~noticias_colombia['titulo'].str.contains('ecuador', case=False) &
                  ~noticias_colombia['titulo'].str.contains('gaza', case=False) &
                  ~noticias_colombia['titulo'].str.contains('españa', case=False) &
                  ~noticias_colombia['titulo'].str.contains('uruguay', case=False) &
                  ~noticias_colombia['titulo'].str.contains('nicaragua', case=False) &
                  ~noticias_colombia['titulo'].str.contains('brasil', case=False))


# Reindexar la serie booleana filtro_no_fenomeno para que coincida con el índice del DataFrame noticias_colombia
filtro_no_pais = filtro_no_pais.reindex(noticias_colombia.index)


# Aplicar el filtro al DataFrame para que no aparezca fenómeno del niño
noticias_colombia = noticias_colombia[filtro_no_pais]

# Que todas las palabras de dias semanas siempre esten en español.
mapeo_dias = {
    'Monday': 'lunes',
    'Tuesday': 'martes',
    'Wednesday': 'miércoles',
    'Thursday': 'jueves',
    'Friday': 'viernes',
    'Saturday': 'sábado',
    'Sunday': 'domingo'
}

Palabras_ciudad ={
    'Bogota' : 'Bogotá'
}




# Reemplazar valores en la columna DiaSemana utilizando el mapeo
noticias_colombia['DiaSemana'] = noticias_colombia['DiaSemana'].replace(mapeo_dias)

# Reemplazando valores en la columna Ciudad que sean palabras Bogota por Bogotá
noticias_colombia['ciudad'] = noticias_colombia['ciudad'].replace(Palabras_ciudad)



#Guardando base de datos procesada de google noticias
noticias_colombia.to_excel('Data/consolidado_noticias.xlsx', index=False)

noticias_colombia.columns
#<h1>TOKENIZACIÓN</h1>
import pandas as pd
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords


# Tokenización
noticias_colombia['tokens'] = noticias_colombia['titulo'].apply(word_tokenize)

# Stop words en español
stop_spanish = set(stopwords.words('spanish'))

# Crear un nuevo DataFrame con una fila por cada palabra y las demás columnas originales
data = []

for i, row in noticias_colombia.iterrows():
    for palabra in row['tokens']:
        # Filtrar stop words
        if palabra.lower() not in stop_spanish:
            # Crear un nuevo diccionario para cada palabra
            nueva_fila = {
                'titulo': row['titulo'],
                'fuente': row['fuente'],
                'ciudad': row['ciudad'],
                'departamento': row['departamento'],
                'maltrato': row['maltrato'],
                'Año': row['Año'],
                'Mes': row['Mes'],
                'DiaSemana': row['DiaSemana'],
                'DiaNumero': row['DiaNumero'],
                'tokens': palabra
            }
            data.append(nueva_fila)

# Nuevo DataFrame
df_resultado = pd.DataFrame(data)

#Limpieza los datos en la variable tokens
## Eliminando caracteres especiales que me trae como tokens

df_resultado['tokens'] = df_resultado['tokens'].str.lstrip('¿') ##Eliminando Caracter que esta al inicio de palabra ejemplo (¿Porque )

df_resultado['tokens'] = df_resultado['tokens'].str.lstrip('¡')  ##Eliminando Caracter que esta al inicio

df_resultado['tokens'] = df_resultado['tokens'].str.lstrip("'")  ##Eliminando Caracter que esta al inicio

df_resultado['tokens'] = df_resultado['tokens'].str.lstrip("´")  ##Eliminando Caracter que esta al inicio


# Creando lista de valores no deseados para eliminar los valores con esos caracteres que esta como tokens
valores_no_deseados = ['-', ',', '–', '—', ';', ':', '?', '.', '...', '’', '‘', '“', '”', '«', '«', '(', ')', '[', ']', '\\', '&', '#', '%', '``', '$', '|', ' ', '!', '»', '•']

# Filtrar las filas que no contienen únicamente los valores no deseados en la columna 'tokens'
df_resultado = df_resultado[~df_resultado['tokens'].isin(valores_no_deseados)]


# Eliminar filas con campos vacíos en la columna 'tokens'
df_resultado = df_resultado[df_resultado['tokens'].str.strip() != '']


# Eliminar filas de la columna 'tokens' que contienen solo números, números con puntos o números con comas
df_resultado = df_resultado[df_resultado['tokens'].apply(lambda x: not x.replace('.', '').replace(',', '').replace('-', '').isdigit())]

#Obtener dataframe de palabras con sus puntuaciones para analisis de sentimientos
from io import StringIO


# URL
url_sentimiento = "https://raw.githubusercontent.com/jboscomendoza/rpubs/master/sentimientos_afinn/lexico_afinn.en.es.csv"

# Lectura de datos
response = requests.get(url_sentimiento)
data = StringIO(response.text)
df_sentimiento = pd.read_csv(data)

# Conteo de palabras repetidas en español y me muestran varias palabras que se repiten. por lo que me llevara problemas a la hora de UNIR.
df_senti_final  = df_sentimiento.value_counts('Palabra').reset_index(name = 'Total').sort_values(by='Total', ascending=False)


# Eliminar duplicados de la columna 'Palabra'
df_sentimiento_fn = df_sentimiento.drop_duplicates(subset='Palabra')


#Uniendo base de datos Tokenizada y Tabla de las palabras con sus puntuaciones de los sentimientos
## Uniendo tabla df_resultado y df_sentimiento_fn

# Unir las dos tablas por la columna 'tokens'
df_resultado_final = pd.merge(df_resultado, df_sentimiento_fn, left_on='tokens', right_on='Palabra', how='left')

# Eliminar la columna 'palabra' si no es necesaria
df_resultado_final = df_resultado_final.drop('Palabra', axis=1)

# Eliminar filas donde la columna 'tokens' está vacía. Esti para eliminar conectores y palabras subjetivas ejemplo. (DE, PARA, NIÑOS, NIÑO)
df_resultado_final = df_resultado_final.dropna(subset=['Puntuacion'])



#Palabras que son sinonimas colocarlas iguales. Ejemplo muerte y muerto, dejarla como muerte.

Palabras_sinonimas = {
    'muerto': 'muerte'
}


# Reemplazando valores en la columna Tokens que sean palabras sinonimas para que solamente sean una.

df_resultado_final['tokens'] = df_resultado_final['tokens'].replace(Palabras_sinonimas)


#Guardando base de datos Final
df_resultado_final.to_excel('Data/df_resultado_final.xlsx', index=False)
#CREANDO DATA PARA MAPA
import geopandas as gpd



ciudades = gpd.read_file("Data/MGN_MPIO_POLITICO/MGN_MPIO_POLITICO.shp")

data_final = pd.read_excel("Data/df_resultado_final.xlsx")

# Cambiando nombre de columna
ciudades = ciudades.rename(columns={'MPIO_CNMBR': 'ciudad'})

# Cambiando nombres en campos de la columnaciudad

ciudades['ciudad'] = ciudades['ciudad'].replace('BOGOTÁ, D.C.', 'BOGOTÁ')
ciudades.loc[ciudades['ciudad'] == 'CARTAGENA DE INDIAS', 'ciudad'] = 'Cartagena'

# Convertir ciudades en tabla1 a mayúsculas
ciudades['ciudad'] = ciudades['ciudad'].str.upper()

# Convertir ciudades en tabla2 a mayúsculas
data_final['ciudad'] = data_final['ciudad'].str.upper()

# Realiza la combinación utilizando la columna 'ciudad'
tabla_combinada = pd.merge(data_final, ciudades[['ciudad', 'geometry']], on='ciudad', how='left')
tabla_filtrada = tabla_combinada.dropna(subset=['ciudad'])
#conteo_por_fuente = data.groupby('fuente').size().reset_index(name='conteo').sort_values(by='conteo', ascending=False).head(20)
palabras_clave = ['muerte', 'accidente', 'abuso', 'abandonado', 'desaparecido','acusado','muerto','hambre','violencia', 'ayuda','crimen','violar']


##Agrupando por ciudad y tokens
grupos_ciudad_palabras = tabla_filtrada.groupby(['ciudad', 'tokens','geometry']).size().reset_index(name='Total').sort_values(by='Total', ascending=False)


#filtrando grupo ciudad palabras... de el vector palabras_clave
grupos_ciudad_palabras = grupos_ciudad_palabras[grupos_ciudad_palabras['tokens'].isin(palabras_clave)]
##Guardando data para Mapas
grupos_ciudad_palabras.to_excel("Data/Consolidado/df_mapas_fn.xlsx", index=False)
