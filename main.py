# Importar bibliotecas de Python
import pandas as pd
from bs4 import BeautifulSoup 
import requests
from datetime import datetime
import openpyxl
import re
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords

# Descargar recursos necesarios de NLTK
import nltk
nltk.download('punkt', quiet=True)
nltk.download('stopwords', quiet=True)

# Función google_Noticias que se conecta a la página de Google Noticias y extrae datos
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

# URLs de noticias en Google Noticias
urls = [
    "https://news.google.com/search?q=ni%C3%B1o&hl=es-419&gl=CO&ceid=CO%3Aes-419",
    "https://news.google.com/search?q=ni%C3%B1a&hl=es-419&gl=CO&ceid=CO%3Aes-419",
    "https://news.google.com/search?q=adolescente&hl=es-419&gl=CO&ceid=CO%3Aes-419",
    "https://news.google.com/search?q=bebe&hl=es-419&gl=CO&ceid=CO%3Aes-419",
    "https://news.google.com/search?q=menor%20de%20edad&hl=es-419&gl=CO&ceid=CO%3Aes-419"
]

# Combinar datos de todas las URLs
noticias_colombia = pd.concat([google_noticias(url) for url in urls], ignore_index=True)

# Validar datos antes de procesar
if noticias_colombia['titulo'].isnull().any():
    print("Warning: Null values detected in 'titulo' column. Filling with empty strings.")
    noticias_colombia['titulo'] = noticias_colombia['titulo'].fillna("")

# Manejo seguro de tokenización
def safe_tokenize(text):
    try:
        return word_tokenize(text)
    except Exception as e:
        print(f"Error tokenizing: {text}, {e}")
        return []

# Tokenización de los títulos
noticias_colombia['tokens'] = noticias_colombia['titulo'].apply(safe_tokenize)

# Descargar stopwords en español
stop_spanish = set(stopwords.words('spanish'))

# Crear un DataFrame con palabras tokenizadas filtrando stopwords
data = []
for _, row in noticias_colombia.iterrows():
    for palabra in row['tokens']:
        if palabra.lower() not in stop_spanish:
            data.append({
                'titulo': row['titulo'],
                'fuente': row['fuente'],
                'tokens': palabra
            })

df_resultado = pd.DataFrame(data)

# Guardar resultados en Excel
df_resultado.to_excel('Data/df_resultado_final.xlsx', index=False)
print('Archivo guardado correctamente.')
