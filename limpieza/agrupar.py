# -*- coding: utf-8 -*-
"""
agrupar.py - Agrupa las noticias que cuentan el MISMO hecho (estilo Gun Violence Archive)
y consolida cada grupo en una fila del registro.

Dos noticias son el mismo hecho si sus titulares se parecen (similitud TF-IDF),
se publicaron con pocos dias de diferencia y no se contradicen en lugar, edad
de la victima ni relacion del agresor. Si comparten un detalle distintivo (un apodo,
el nombre de un colegio, "62 anos", "20 meses") basta con un parecido minimo.
Ver CODEBOOK.md, seccion 7.
"""

import re
from collections import Counter

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .reglas import ORDEN_ESTADO, grupo_edad, norm

VENTANA_DIAS = 10
# un caso se cubre por semanas (captura -> judicializacion -> condena): si dos noticias
# comparten un nombre propio raro, se permite una ventana mas larga
VENTANA_DIAS_FUERTE = 45
# 2a pasada: las noticias de REACCION (Procuraduria, Petro, ICBF, alcaldia) casi no repiten los detalles del
# caso y la 1a pasada las deja aparte. Se unen GRUPOS ya formados, mas parecidos en conjunto (todos sus
# titulares juntos) y muy cercanos en el tiempo. La similitud exigida depende de cuanto lugar tengan en comun.
VENTANA_DIAS_GRUPOS = 3
UMBRAL_GRUPOS_MPIO = 0.20          # mismo municipio
UMBRAL_GRUPOS_MPIO_GRANDE = 0.22   # mismo municipio grande (Bogota, Medellin...)
UMBRAL_GRUPOS_DPTO = 0.35          # a uno le falta el municipio
UMBRAL_GRUPOS_SIN_LUGAR = 0.50     # a ninguno le consta el lugar
STOP_ES = """a al algo ante con contra de del desde donde durante e el ella ellos en entre era es esa
ese eso esta este esto fue ha han hasta hay la las le les lo los mas me mi muy no nos o otra otro para
pero por que se sea ser si sin sobre su sus tambien te tras tu un una uno y ya""".split()
# Si las noticias de un hecho lo describen distinto, se queda el subtipo mas especifico
SUBTIPO_PRIORIDAD = ["explotacion_sexual_comercial", "material_abuso_digital", "acceso_carnal",
                     "acoso_sexual", "abuso_sexual", "sin_especificar"]


# "Otro gringo con cadena perpetua", "nuevo caso": la propia noticia dice que es OTRO hecho, no se une a ninguno
OTRO_CASO = re.compile(r"\botr[oa]s? (gringo|extranjero|estadounidense|capturado|hombre|sacerdote|profesor|docente|"
                       r"abusador|agresor|pastor|medico|caso|sujeto|detenido|imputado)\b|\bnuevo caso\b|"
                       r"\bsegundo (caso|capturado|detenido)\b|\bnueva captura\b")


# Palabras tan frecuentes en estas noticias que no distinguen un hecho de otro
GENERICAS = set("""abuso abusos abusar abusado abusada abusador sexual sexuales sexualmente menor menores
nina ninas nino ninos capturan capturado capturada captura hombre hombres presunto presunta
presuntamente carcel prision fiscalia policia violencia delito delitos contra senalado senalada
judicializado judicializan condenado condenan condena victima victimas casos investigan
investigacion denuncia denuncian adolescente adolescentes agresion violacion violada violador
sujeto mujer madre padre familia colegio escuela estudiante estudiantes docente profesor
cometidos realizar habria habrian enviado enviaron mandaron actos
icbf bienestar familiar fiscalia policia medicina legal gaula sijin dijin inpec unicef procuraduria
defensoria personeria alcaldia gobernacion colombia tiktok instagram facebook whatsapp youtube
telegram video""".split())
# Un nombre propio es "raro" si aparece en pocas noticias de TODO el periodo (no solo las
# de violencia sexual). El limite deja pasar apodos de casos muy cubiertos ("Vaquerito")
RARA_MAX_NOTICIAS = 25
# Numeros distintivos, cada uno con su tipo para no confundir "17 anos de prision" con
# "adolescente de 17 anos"
CONDENA_RE = re.compile(r"\b(\d{1,3})( y medio)? anos( y medio)? de (prision|carcel)"
                        r"|\bcondena\w* a (?:mas de )?(\d{1,3}) anos")
EDAD_ADULTA_RE = re.compile(r"\bde (\d{2,3}) anos\b(?! (?:y medio )?de (?:prision|carcel))")
MESES_RE = re.compile(r"\b(\d{1,2}) meses\b")


def _vacio(v):
    return v is None or (isinstance(v, float) and np.isnan(v)) or v in ("", "ND")


def _palabras(t):
    return set(re.findall(r"[a-z]{5,}", t)) - set(STOP_ES) - GENERICAS


def _numeros(t):
    condenas = {n for m in CONDENA_RE.finditer(t) for n in (m.group(1), m.group(5)) if n}
    return ({("condena", n) for n in condenas}
            | {("edad", n) for n in EDAD_ADULTA_RE.findall(t) if int(n) >= 18}
            | {("meses", n) for n in MESES_RE.findall(t)})


def _nombres_propios(titulo):
    """Palabras con mayuscula que no estan al inicio del titular (apodos, colegios, personas)."""
    palabras = re.findall(r"\w+", str(titulo))
    return {norm(p) for p in palabras[1:] if p[0].isupper()}


def _palabras_de_lugar(fila):
    """Los lugares reconocidos en el titular no son un detalle del caso (de eso ya se encargan
    las reglas de ubicacion): "Bolivar" o "Cartagena" no prueban que dos notas sean el mismo hecho."""
    campos = ("municipio", "departamento", "lugar_no_confirmado", "candidatos")
    return set(norm(" ".join(str(fila[c]) for c in campos if not _vacio(fila[c]))).split())


def _evidencia(df, corpus):
    """Detalles distintivos de cada noticia: nombres propios raros en el periodo y numeros tipificados."""
    frecuencia = Counter(tok for t in corpus for tok in _palabras(t))
    raras = [({tok for tok in _palabras(fila["texto_norm"]) if frecuencia[tok] <= RARA_MAX_NOTICIAS}
              & _nombres_propios(fila["titulo"])) - _palabras_de_lugar(fila)
             for fila in df.to_dict("records")]
    return raras, [_numeros(t) for t in df["texto_norm"]]


# La edad de un adulto o los meses de un bebe distinguen un caso; los anos de condena no
# (20 anos es una condena comun), pero si dos noticias dan condenas distintas no son el mismo caso
TIPOS_FUERTES = {"edad", "meses"}


def _numeros_fuertes(x, y):
    return any(t in TIPOS_FUERTES for t, _ in x & y)


def _choque_numeros(x, y):
    """Hay choque si las dos noticias dan un mismo tipo de numero con valores distintos."""
    for tipo in {t for t, _ in x} & {t for t, _ in y}:
        if not ({v for t, v in x if t == tipo} & {v for t, v in y if t == tipo}):
            return True
    return False


def _mismo_depto(a, b):
    if not _vacio(a["cod_dpto"]) and a["cod_dpto"] == b["cod_dpto"]:
        return True
    # el departamento que cubre un medio local (Q'hubo Medellin) cuenta como pista
    return any(not _vacio(x["departamento"]) and x["departamento"] == y["depto_probable_medio"]
               for x, y in ((a, b), (b, a)))


def _compatibles(a, b, fuerte):
    """Dos noticias que se contradicen nunca pueden ser el mismo hecho."""
    if "ND" not in (a["ambito"], b["ambito"]) and a["ambito"] != b["ambito"]:
        return False
    for campo in ("cod_dpto", "agresor_relacion"):
        if not _vacio(a[campo]) and not _vacio(b[campo]) and a[campo] != b[campo]:
            return False
    # municipios distintos del mismo depto solo con evidencia fuerte (area metropolitana)
    if not _vacio(a["cod_divipola"]) and not _vacio(b["cod_divipola"]) \
            and a["cod_divipola"] != b["cod_divipola"] and not fuerte:
        return False
    if not _vacio(a["victima_edad"]) and not _vacio(b["victima_edad"]) \
            and abs(a["victima_edad"] - b["victima_edad"]) > 1:
        return False
    return True


def _umbral(a, b, fuerte):
    """Similitud minima exigida: baja si coinciden el municipio, la edad o un detalle distintivo."""
    if fuerte:
        return 0.10
    if not _vacio(a["cod_divipola"]) and a["cod_divipola"] == b["cod_divipola"]:
        u = 0.38 if a["mpio_grande"] else 0.22  # en Cartagena hay muchos casos; en Isnos, pocos
    elif _mismo_depto(a, b):
        u = 0.38
    else:
        u = 0.55  # sin lugar en comun, dos titulares genericos se parecen facilmente
    if not _vacio(a["victima_edad"]) and a["victima_edad"] == b["victima_edad"]:
        u -= 0.08
    return u


def agrupar(df, corpus):
    """Recibe noticias ORDENADAS por fecha y devuelve el numero de grupo (hecho) de cada una.
    `corpus`: titulares normalizados de TODO el periodo, para medir que palabras son raras."""
    n = len(df)
    if n == 0:
        return np.array([], dtype=int)
    vec = TfidfVectorizer(ngram_range=(1, 2), stop_words=STOP_ES, sublinear_tf=True)
    sim = cosine_similarity(vec.fit_transform(df["texto_norm"]))
    filas = df.to_dict("records")
    fechas = pd.to_datetime(df["fecha"]).values
    raras, numeros = _evidencia(df, corpus)
    aislada = [bool(OTRO_CASO.search(t)) for t in df["texto_norm"]]  # la noticia misma dice que es otro hecho

    padre = list(range(n))

    # lo que ya se sabe de cada grupo, para no encadenar noticias incompatibles (A~B, B~C, A!=C)
    def conjunto(campo):
        return [{f[campo]} if not _vacio(f[campo]) else set() for f in filas]

    mpios, dptos, edades = conjunto("cod_divipola"), conjunto("cod_dpto"), conjunto("victima_edad")
    ambitos, agresores = conjunto("ambito"), conjunto("agresor_relacion")
    nums = [set(x) for x in numeros]

    def raiz(x):
        while padre[x] != x:
            padre[x] = padre[padre[x]]
            x = padre[x]
        return x

    for i in range(n):
        for j in range(i + 1, n):
            dias = (fechas[j] - fechas[i]) / np.timedelta64(1, "D")
            if dias > VENTANA_DIAS_FUERTE:
                break  # vienen ordenadas: las siguientes estan aun mas lejos
            if aislada[i] or aislada[j]:
                continue
            nombre_comun = bool(raras[i] & raras[j])
            fuerte = nombre_comun or _numeros_fuertes(numeros[i], numeros[j])
            if dias > (VENTANA_DIAS_FUERTE if nombre_comun else VENTANA_DIAS):
                continue
            if _choque_numeros(numeros[i], numeros[j]):
                continue
            if not _compatibles(filas[i], filas[j], fuerte) \
                    or sim[i, j] < _umbral(filas[i], filas[j], fuerte):
                continue
            ri, rj = raiz(i), raiz(j)
            if ri == rj:
                continue
            if dptos[ri] and dptos[rj] and not (dptos[ri] & dptos[rj]):
                continue
            if mpios[ri] and mpios[rj] and not (mpios[ri] & mpios[rj]) and not fuerte:
                continue
            if edades[ri] and edades[rj] and not any(abs(x - y) <= 1 for x in edades[ri] for y in edades[rj]):
                continue
            if {"colombia", "exterior"} <= (ambitos[ri] | ambitos[rj]):
                continue
            if agresores[ri] and agresores[rj] and agresores[ri] != agresores[rj]:
                continue
            if _choque_numeros(nums[ri], nums[rj]):
                continue
            padre[ri] = rj
            for c in (mpios, dptos, edades, ambitos, agresores, nums):
                c[rj] |= c[ri]

    # ---- 2a pasada: unir grupos de noticias de reaccion al hecho original
    miembros = {}
    for i in range(n):
        miembros.setdefault(raiz(i), []).append(i)
    raices = list(miembros)
    if len(raices) > 1:
        textos = df["texto_norm"].tolist()
        docs = [" ".join(textos[k] for k in miembros[r]) for r in raices]
        vec2 = TfidfVectorizer(ngram_range=(1, 2), stop_words=STOP_ES + sorted(GENERICAS), sublinear_tf=True)
        sim2 = cosine_similarity(vec2.fit_transform(docs))
        ini = np.array([min(fechas[k] for k in miembros[r]) for r in raices], dtype="datetime64[D]")
        fin = np.array([max(fechas[k] for k in miembros[r]) for r in raices], dtype="datetime64[D]")
        grande = [any(filas[k]["mpio_grande"] for k in miembros[r]) for r in raices]
        candidatos = []
        for a_, b_ in zip(*np.where(np.triu(sim2, 1) >= UMBRAL_GRUPOS_MPIO)):
            hueco = max(ini[a_], ini[b_]) - min(fin[a_], fin[b_])
            if hueco / np.timedelta64(1, "D") <= VENTANA_DIAS_GRUPOS:
                candidatos.append((sim2[a_, b_], a_, b_))
        for sim_ab, a_, b_ in sorted(candidatos, reverse=True):
            ra, rb = raiz(raices[a_]), raiz(raices[b_])
            if any(aislada[k] for k in miembros[raices[a_]] + miembros[raices[b_]]):  # nunca se unen en la 1a pasada
                continue
            if ra == rb:
                continue
            if mpios[ra] and mpios[rb]:
                if not (mpios[ra] & mpios[rb]):
                    continue
                minimo = UMBRAL_GRUPOS_MPIO_GRANDE if grande[a_] or grande[b_] else UMBRAL_GRUPOS_MPIO
            elif dptos[ra] and dptos[rb]:
                if not (dptos[ra] & dptos[rb]):
                    continue
                minimo = UMBRAL_GRUPOS_DPTO
            elif mpios[ra] or mpios[rb] or dptos[ra] or dptos[rb]:
                minimo = UMBRAL_GRUPOS_DPTO
            else:
                minimo = UMBRAL_GRUPOS_SIN_LUGAR
            if sim_ab < minimo:
                continue
            if {"colombia", "exterior"} <= (ambitos[ra] | ambitos[rb]):
                continue
            if edades[ra] and edades[rb] and not any(abs(x - y) <= 1 for x in edades[ra] for y in edades[rb]):
                continue
            if agresores[ra] and agresores[rb] and agresores[ra] != agresores[rb]:
                continue
            if _choque_numeros(nums[ra], nums[rb]):
                continue
            padre[ra] = rb
            for c in (mpios, dptos, edades, ambitos, agresores, nums):
                c[rb] |= c[ra]
            grande[b_] = grande[b_] or grande[a_]
    return np.array([raiz(i) for i in range(n)])


def _o_vacio(v):
    return "" if v == "ND" else v


def _moda(valores, prioridad=None):
    vals = [v for v in valores if not _vacio(v)]
    if not vals:
        return "ND"
    conteo = Counter(vals)
    tope = max(conteo.values())
    empatados = [v for v in conteo if conteo[v] == tope]
    if prioridad:
        empatados.sort(key=lambda v: prioridad.index(v) if v in prioridad else len(prioridad))
    return empatados[0]


def _ambito_hecho(g):
    """Ambito del hecho por MAYORIA de sus noticias (antes bastaba UNA noticia de Colombia: un hecho de
    Panama se colo por una nota de otro caso). Para ser Colombia debe ganarle al exterior y, ademas, tener un
    lugar confirmado en el titular o al menos un tercio de las noticias."""
    n_col = int((g["ambito"] == "colombia").sum())
    n_ext = int((g["ambito"] == "exterior").sum())
    if n_col == 0 and n_ext == 0:
        return "ND"
    if n_ext > n_col or (n_ext == n_col and n_ext > 0):
        return "exterior"
    confirmado = ((g["ambito"] == "colombia") & (g["ambito_criterio"] == "lugar")
                  & g["geo_precision"].isin([1, 2])).any()
    return "colombia" if confirmado or n_col * 3 >= len(g) else "ND"


def consolidar(df, grupos, prefijo="VS"):
    """Una fila por hecho. Devuelve (registro, {grupo: id_hecho})."""
    df = df.assign(grupo=grupos)
    filas = []
    for grupo, g in df.groupby("grupo"):
        g = g.sort_values("fecha")
        presentes = set(g["subtipo"])
        subtipo = next(s for s in SUBTIPO_PRIORIDAD if s in presentes)

        sexos = set(g["victima_sexo"]) - {"ND"}
        if "mixto" in sexos or {"F", "M"} <= sexos:
            sexo = "mixto"
        else:
            sexo = sexos.pop() if sexos else "ND"

        edad = _moda(g["victima_edad"].tolist())
        edad = None if edad == "ND" else int(edad)
        grupo_ed = grupo_edad(edad, "") if edad is not None else _moda(g["victima_grupo_edad"].tolist())

        relacion = _moda(g["agresor_relacion"].tolist())
        agresor_grp = g.loc[g["agresor_relacion"] == relacion, "agresor_grupo"].iloc[0] \
            if relacion != "ND" else "ND"

        lugar = g.sort_values("geo_precision").iloc[0]  # la ubicacion mas precisa
        ambito = _ambito_hecho(g)
        estado = max(g["estado"], key=lambda e: ORDEN_ESTADO.get(e, 0))
        muerte = bool(g["muerte_victima"].any())
        fuentes = list(dict.fromkeys(g["fuente"].fillna("").astype(str)))
        confianza = round(float(g["confianza"].max()), 2)

        filas.append({
            "grupo": grupo,
            "fecha_hecho": g["fecha"].min().date(),
            "ultima_publicacion": g["fecha"].max().date(),
            "tipo_vulneracion": g["tipo_vulneracion"].iloc[0],
            "subtipo": subtipo,
            "victima_sexo": sexo,
            "victima_edad": edad,
            "victima_grupo_edad": grupo_ed,
            "num_victimas": int(g["num_victimas"].max()),
            "agresor_relacion": relacion,
            "agresor_grupo": agresor_grp,
            "municipio": lugar["municipio"],
            "cod_divipola": lugar["cod_divipola"],
            "departamento": lugar["departamento"],
            "cod_dpto": lugar["cod_dpto"],
            "geo_precision": int(lugar["geo_precision"]),
            "lat": lugar["lat"],
            "lon": lugar["lon"],
            "ambito": ambito,
            "ambito_criterio": _moda(g.loc[g["ambito"] == ambito, "ambito_criterio"].tolist()),
            "candidatos_ubicacion": lugar["candidatos"],
            "lugar_no_confirmado": _o_vacio(_moda(g["lugar_no_confirmado"].tolist())),
            "depto_probable_medio": _o_vacio(_moda(g["depto_probable_medio"].tolist())),
            "estado": estado,
            "muerte_victima": muerte,
            "n_fuentes": len([f for f in fuentes if f]),
            "n_noticias": len(g),
            "fuentes": " | ".join(fuentes),
            "titular_principal": g["titulo"].iloc[0],
            "titulares": " || ".join(g["titulo"]),
            "links": " | ".join(g["link"].fillna("").astype(str)),
            "confianza": confianza,
            "requiere_revision": muerte or confianza < 0.4
                                 or (ambito == "colombia" and int(lugar["geo_precision"]) == 3),
        })

    reg = pd.DataFrame(filas).sort_values(["fecha_hecho", "grupo"]).reset_index(drop=True)
    # id del estilo VS-2026-08-0001 (consecutivo por mes)
    mes = pd.to_datetime(reg["fecha_hecho"]).dt.strftime("%Y-%m")
    consecutivo = reg.groupby(mes).cumcount() + 1
    reg.insert(0, "id_hecho", [f"{prefijo}-{m}-{c:04d}" for m, c in zip(mes, consecutivo)])
    id_por_grupo = dict(zip(reg["grupo"], reg["id_hecho"]))
    return reg.drop(columns="grupo"), id_por_grupo
