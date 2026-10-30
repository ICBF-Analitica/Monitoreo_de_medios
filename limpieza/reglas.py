# -*- coding: utf-8 -*-
"""
reglas.py - Reglas de extraccion del codebook (piloto: violencia sexual).

Todas las reglas trabajan sobre el texto NORMALIZADO (minusculas, sin tildes, ñ -> n),
por eso los patrones se escriben sin tildes: "nina", "anos", "violacion".
Para ajustar el comportamiento basta con editar las listas de este archivo.
Ver CODEBOOK.md para la definicion de cada campo.
"""

import re
from unidecode import unidecode


def norm(texto):
    """Minusculas, sin tildes y con espacios simples."""
    return re.sub(r"\s+", " ", unidecode(str(texto)).lower()).strip()


# ----------------------------------------------------------------------------
# 1. Violencia sexual: deteccion y subtipo
# ----------------------------------------------------------------------------
# Frases que parecen violencia sexual pero no lo son
EXCLUSIONES_VS = re.compile(
    r"violacion(es)? (de|a|al|del) (los |la |el )?(derechos?|ley|norma|tutela|privacidad|"
    r"debido|cese|acuerdo|datos|domicilio|reglamento|codigo|protocolo|medida)"
    r"|abusos? de (autoridad|poder|confianza|funciones|posicion)"
    r"|abusos? policial"
)

# Orden = prioridad: el primero que coincida define el subtipo
SUBTIPOS_VS = [
    ("explotacion_sexual_comercial",
     r"explotacion sexual|explotad[ao]s? sexualmente|proxenet|prostitu|turismo sexual|"
     r"esclavitud sexual|trata de (personas|menores) con fines|escnna"),
    ("material_abuso_digital",
     r"pornografi|material de abuso|contenido sexual|imagenes? (intimas|sexuales|sexualizadas)|"
     r"sextorsion|grooming|videos? (sexuales|intimos)|fotos? intimas"),
    ("acceso_carnal",
     r"\bviolacion|\bviolad[ao]s?\b|\bviolo\b|\bviolaron\b|\bviolar\b|\bviolador|acceso carnal"),
    ("acoso_sexual",
     r"acoso sexual|acosad[ao]s? sexualmente|\bacosador"),
    ("abuso_sexual",
     r"abus\w* sexual|actos? sexual|tocamientos|agresion sexual|agredid[ao]s? sexualmente|"
     r"actos? libidinoso|\babus(o|aron|ar|aba|ado|ada|ados|adas) de\b|\babusad[ao]s?\b|"
     r"\babusador|\babuso a\b"),
    ("sin_especificar",
     r"violencia sexual|delitos? sexual|crimen(es)? sexual|agresor sexual|depredador sexual"),
]
SUBTIPOS_VS = [(nombre, re.compile(patron)) for nombre, patron in SUBTIPOS_VS]


def subtipo_violencia_sexual(t):
    """Devuelve el subtipo de violencia sexual, o None si el texto no trata de eso."""
    limpio = EXCLUSIONES_VS.sub(" ", t)
    for nombre, patron in SUBTIPOS_VS:
        if patron.search(limpio):
            return nombre
    return None


# ----------------------------------------------------------------------------
# 2. Tipo de registro: hecho / cifras / prevencion_politica / otro
# ----------------------------------------------------------------------------
_VICTIMA = (r"(nina|nino|menor|adolescente|bebe|estudiante|hija|hijo|hijastra|hijastro|sobrina|"
            r"sobrino|nieta|nieto|alumna|alumno|chica|chico|jovencita|victima|pequena|pequeno)")

OTRO = re.compile(r"\bpelicula|\bserie\b|\bdocumental|\blibro\b|\bnetflix|\bcuando era (nina|nino)|"
                  r"\bcancion|\bobra de teatro|\bopinion\b|\bcolumna\b|\bpodcast|\bnovela\b|"
                  r"\bactriz|\bactor\b|\bcantante")
PREVENCION = re.compile(r"\bprevenir|\bprevencion|\bcampana|\bconsejos|"
                        r"\bcomo (proteger|prevenir|hablar|identificar|detectar|actuar)|"
                        r"\bproyecto de ley|\bcongreso|\bforo\b|\bcapacitacion|\bruta de atencion|"
                        r"\bpedagog|\bsensibiliz|\bpolitica publica|\bdebate\b|\bsenales de alerta|"
                        r"\bguia\b|\bestrategia|\bjornada|\btaller|\bvacio legal|\basi cambio|"
                        r"\bla forma en que|\bque es (el|la)\b|\bclaves para|\blo que (debe|debes) saber|"
                        r"\bexpertos (advierten|explican|alertan)")
CIFRAS = re.compile(r"\bcifras?\b|\baumenta|\bdisminu|\bpor ciento\b|%|\bestadistic|\binforme\b|"
                    r"\bbalance\b|\bindices?\b|\bcada (dia|hora|semana)\b|\bmiles de\b|"
                    r"\bmas de \d[\d\.]* (casos|ninos|ninas|menores|denuncias|victimas)|"
                    r"\bcasos (este|en el) ano")
# Senales de que se habla de un caso concreto
EVENTO_FUERTE = re.compile(r"\bcaptur|\bconden|\bjudicializ|\bimput|\baseguramiento|\barrest|"
                           r"\bdetenid|\baprehend|\brescat|\basesin|\bfeminicid|\bse entrego|"
                           r"\bprofugo|\bsentencia|\b" + _VICTIMA + r"(?:s|es)? de \w+ (anos|meses)")
EVENTO_DEBIL = re.compile(r"\bdenunci|\bpresunt|\bsenalad|\bacusad|\bsospechos|\binvestig|"
                          r"\bhallan|\bmurio|\babusaron|\babuso de\b|\bviolo\b|\bviolaron|\bcarcel|"
                          r"\bprision|\bbuscan a|\bpadrastro|\bprofesor|\bdocente")
VICTIMA_RE = re.compile(r"\b" + _VICTIMA + r"(?:s|es)?\b")


# Resumenes de operativos y balances ("ya van 85 en lo corrido de 2026"): no son UN hecho
RESUMEN = re.compile(r"\bya van \d|\bvan \d+ (en|durante|este)|\ben lo corrido\b|\bofensiva (contra|de)\b|"
                     r"\blo que (las )?redes (sociales )?(les )?(le )?muestra")


def tipo_registro(t):
    """Clasifica la noticia segun el codebook (seccion 1)."""
    if OTRO.search(t):
        return "otro"
    if RESUMEN.search(t):
        return "cifras"
    fuerte = bool(EVENTO_FUERTE.search(t))
    if PREVENCION.search(t) and not fuerte:
        return "prevencion_politica"
    if CIFRAS.search(t) and not fuerte:
        return "cifras"
    if fuerte or EVENTO_DEBIL.search(t) or VICTIMA_RE.search(t):
        return "hecho"
    return "otro"


# ----------------------------------------------------------------------------
# 3. Victima: sexo, edad, grupo de edad, numero
# ----------------------------------------------------------------------------
FEM = re.compile(r"\b(nina|ninas|una menor|la menor|una adolescente|la adolescente|hija|hijas|"
                 r"hijastra|hijastras|sobrina|sobrinas|nieta|nietas|alumna|alumnas|jovencita|"
                 r"jovencitas|una bebe|la bebe|bebita|una estudiante|la estudiante|chica|chicas|"
                 r"pequena|pequenas|nenita)\b")
MAS = re.compile(r"\b(nino|un menor|el menor|un adolescente|el adolescente|hijo|hijastro|sobrino|"
                 r"nieto|alumno|un bebe|el bebe|un estudiante|el estudiante|chico|pequeno)\b")

NUMEROS = {"un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6,
           "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12, "trece": 13,
           "catorce": 14, "quince": 15, "dieciseis": 16, "diecisiete": 17}

EDAD_RE = re.compile(r"\b" + _VICTIMA + r"(?:s|es)?\b(?:\s+\w+){0,3}?\s+de\s+"
                     r"(?:apenas\s+|solo\s+|tan solo\s+|escasos\s+)?"
                     r"(\d{1,2}|" + "|".join(NUMEROS) + r")\s+(anos|ano|meses|mes|dias)\b")
# "acto sexual con menor de 14 anos" es una categoria legal, no la edad de la victima
LEGAL_14 = re.compile(r"\b(con|a|de|contra) menor(es)? de (14|catorce) anos")

_MAS_NUMEROS = {**NUMEROS, "veinte": 20, "treinta": 30, "cien": 100}
NUM_VICT_RE = re.compile(r"\b(\d{1,3}|" + "|".join(_MAS_NUMEROS) + r")\s+(menores|ninas|ninos|"
                         r"estudiantes|victimas|adolescentes|hermanas|hermanos|hermanitas|"
                         r"hermanitos|alumnas|alumnos|hijas|hijos|nietas|sobrinas|bebes)\b")


# Un adolescente tambien puede ser el AGRESOR ("Un adolescente es aprehendido por..."):
# esas menciones se quitan antes de buscar el sexo y la edad de la victima
AGRESOR_MENOR = re.compile(
    r"\b(aprehend\w*|captur\w*|judicializ\w*|acus\w*|senal\w*|conden\w*|deten\w*|arrest\w*)\s+"
    r"(a |al )?(un |una |el |la |dos |tres )?(adolescentes?|menor(es)? de edad)\b"
    r"|\b(un |una |el |la )?(adolescentes?|menor(es)? de edad)\b(?:\s+\w+){0,2}?\s+"
    r"(es |fue |son |fueron |habria |seria )?(aprehendid|capturad|acusad|senalad|judicializad|"
    r"detenid|condenad|requerid|violado|abusado|abuso\b|violo\b)")


def _sin_agresor_menor(t):
    return AGRESOR_MENOR.sub(" ", t)


def victima_sexo(t):
    t = _sin_agresor_menor(t)
    f, m = bool(FEM.search(t)), bool(MAS.search(t))
    if f and m:
        return "mixto"
    if f:
        return "F"
    if m:
        return "M"
    return "ND"


def victima_edad(t):
    """Edad de la victima en anos (bebes = 0). None si no se menciona."""
    m = EDAD_RE.search(LEGAL_14.sub(" ", _sin_agresor_menor(t)))
    if not m:
        return None
    valor, unidad = m.group(2), m.group(3)
    n = int(valor) if valor.isdigit() else NUMEROS[valor]
    return 0 if unidad.startswith(("mes", "dia")) else n


def grupo_edad(edad, t):
    """Ciclo vital segun la Ley 1098 de 2006."""
    if edad is not None:
        if edad <= 5:
            return "primera_infancia"
        if edad <= 11:
            return "infancia"
        if edad <= 17:
            return "adolescencia"
        return "adulto"
    if re.search(r"\bbeb(e|es|ita)\b|\brecien nacid|\blactante", t):
        return "primera_infancia"
    if re.search(r"\badolescente", t):
        return "adolescencia"
    return "ND"


def num_victimas(t):
    m = NUM_VICT_RE.search(t)
    if not m:
        return 1
    v = m.group(1)
    return max(int(v) if v.isdigit() else _MAS_NUMEROS.get(v, 1), 1)


# ----------------------------------------------------------------------------
# 4. Relacion del presunto agresor
# ----------------------------------------------------------------------------
_VERBO_AGRESOR = (r"(abuso|abusaba|abusaron|violo|violaba|agredio|explotaba|vendia|acosaba|tocaba|"
                  r"acusad|senalad|capturad|condenad|judicializad|investigad|enviad|procesad|"
                  r"denunciad|detenid|imputad)")
_CAPTURA_DE = (r"(capturan|captura|condenan|judicializan|detienen|arrestan|procesan|imputan|carcel para|"
               r"acuso|acusan|acusa|investigan a)")


def _como_agresor(palabra):
    """Una palabra de parentesco solo cuenta si aparece en rol de agresor
    (evita confundir 'el padre denuncio' o 'descubierto por la madre' con 'el padre abuso')."""
    return re.compile(
        rf"\b(abusad|violad|agredid|explotad|vendid|ultrajad|acosad|maltratad)\w*\s+(sexualmente\s+)?"
        rf"por (su|el|la|un|una|propio|propia) ({palabra})\b"
        rf"|\ba manos de (su|el|la|un|una|propio|propia) ({palabra})\b"
        rf"|\b({palabra})s?\b(?:\s+\w+){{0,3}}?\s+(que |quien )?(habria |presuntamente )?{_VERBO_AGRESOR}"
        rf"|\b{_CAPTURA_DE} (a |al )?(un |una |su |el |la )?({palabra})\b")


# (relacion, grupo, patron). Orden = prioridad.
AGRESORES = [
    ("padrastro", "familiar",
     re.compile(r"\bpadrastro|\bcompanero (sentimental )?de (su|la) madre|\bpareja de (su|la) madre")),
    ("madrastra", "familiar", re.compile(r"\bmadrastra")),
    ("padre", "familiar", _como_agresor(r"padre|papa|progenitor")),
    ("madre", "familiar", _como_agresor(r"madre|mama|progenitora")),
    ("abuelo", "familiar", _como_agresor(r"abuelo|abuela")),
    ("tio", "familiar", _como_agresor(r"tio|tia")),
    ("hermano", "familiar", _como_agresor(r"hermano|hermana|hermanastro|medio hermano")),
    ("primo", "familiar", _como_agresor(r"primo|prima")),
    ("cunado", "familiar", _como_agresor(r"cunado|cunada")),
    ("familiar", "familiar", _como_agresor(r"familiar|pariente")),
    ("docente", "institucional",
     re.compile(r"\bdocente|\bprofesor|\bmaestr[oa]\b|\brector\b|\bcoordinador del? colegio|\borientador")),
    ("religioso", "institucional",
     re.compile(r"\bsacerdote|\bcura\b|\bpastor\b|\bobispo|\bpresbitero|\bseminarista|\breligios[oa]\b")),
    ("entrenador", "institucional", re.compile(r"\bentrenador|\binstructor")),
    ("policia_militar", "institucional",
     re.compile(r"\b(patrullero|policia|soldado|militar|uniformado|sargento|teniente|subintendente|"
                r"intendente)\b(?:\s+\w+){0,3}?\s+(acusado|senalado|capturado|condenado|investigado|"
                r"denunciado|judicializado|habria|abuso|violo)")),
    ("servidor_publico", "institucional",
     re.compile(r"\b(funcionario|concejal|alcalde|exalcalde|diputado|personero|servidor publico|"
                r"defensor de familia|contratista del icbf|madre comunitaria)\b")),
    ("conductor", "institucional",
     re.compile(r"\bconductor|\btransportador|\bruta escolar|\btaxista|\bmototaxista")),
    ("vigilante", "entorno_cercano", re.compile(r"\bvigilante|\bcelador")),
    ("cuidador", "entorno_cercano", re.compile(r"\bcuidador(a)?\b|\bniner[oa]s?\b")),
    ("vecino", "entorno_cercano", re.compile(r"\bvecin[oa]\b")),
    ("pareja", "entorno_cercano", re.compile(r"\bnovio|\bpareja sentimental|\bexpareja")),
    ("amigo", "entorno_cercano",
     re.compile(r"\bamigo de (la|su) familia|\bconocido de la familia|\bamigo de su (padre|madre|papa|mama)")),
    ("extranjero", "extranjero_turista",
     re.compile(r"\bextranjer|\bturista|\bgringo|\bestadounidense|\bnorteamericano|\bcanadiense|"
                r"\beuropeo|\bitaliano|\bisraeli|\bholandes|\baleman\b|\bbritanico")),
    ("grupo_armado", "grupo_armado",
     re.compile(r"\bdisidencia|\beln\b|\bclan del golfo|\bfarc\b|\bgrupo armado|\bguerriller|"
                r"\bparamilitar|\bautodefensas|\btren de aragua")),
    ("desconocido", "desconocido", re.compile(r"\bdesconocid[oa]s?\b|\bextrano\b")),
]

# Si no se nombra al agresor, a veces se deduce de la victima:
# "abuso de su nieta" -> abuelo, "delitos sexuales contra su hijastra" -> padrastro
INFERIDO_RE = re.compile(
    r"\b(abus\w*|viol\w*|agredi\w*|explot\w*|acos\w*|embaraz\w*|sexual\w*)\s+(?:\w+\s+){0,2}?"
    r"(de|a|contra)\s+(?P<pos>(sus?|las|los)\s+)?(?:(dos|tres|cuatro|cinco|\d+)\s+)?"
    r"(?:(propias?|propios?)\s+)?(?P<kin>hijastr|niet|sobrin|hij|herman)")
INFERIDO = {"hijastr": ("padrastro", "familiar"), "niet": ("abuelo", "familiar"),
            "sobrin": ("tio", "familiar"), "hij": ("padre", "familiar"),
            "herman": ("hermano", "familiar")}
# "abusaron de dos hermanas" no dice quien fue: hija/hermano solo se infieren con "su/sus"
SOLO_CON_POSESIVO = {"hij", "herman"}
# "simulando ser guerrillero" no lo hace miembro de un grupo armado
SIMULACION = re.compile(r"\b(simulando|fingiendo|haciendose pasar por|se hacia pasar por|disfrazado de)\b")
NO_SI_SIMULA = {"grupo_armado", "policia_militar", "servidor_publico"}


def agresor(t):
    """Devuelve (relacion, grupo)."""
    simula = bool(SIMULACION.search(t))
    for relacion, grupo, patron in AGRESORES:
        if simula and relacion in NO_SI_SIMULA:
            continue
        if patron.search(t):
            return relacion, grupo
    m = INFERIDO_RE.search(t)
    if m:
        posesivo = (m.group("pos") or "").strip() in ("su", "sus")
        if posesivo or m.group("kin") not in SOLO_CON_POSESIVO:
            return INFERIDO[m.group("kin")]
    return "ND", "ND"


# ----------------------------------------------------------------------------
# 5. Estado del caso y muerte de la victima
# ----------------------------------------------------------------------------
# Orden = avance del caso; se queda el mas avanzado que aparezca
ESTADOS = [
    ("denuncia", re.compile(r"\bdenunci|\binvestig|\bindignacion")),
    ("rescate", re.compile(r"\brescat|\bicbf (asumio|tomo|activo|inicio)|\brestablecimiento|"
                           r"\bmedida de proteccion")),
    ("captura", re.compile(r"\bcaptur|\bdetenid|\barrest|\baprehend|\bse entrego|\bcayo\b|\bcayeron")),
    ("judicializacion", re.compile(r"\bjudicializ|\bimput|\baseguramiento|\bcarcel (preventiva|intramural)|"
                                   r"\bcargos\b|\bllamado a juicio|\ba la carcel\b|\ba prision\b|"
                                   r"\b(envian|enviaron|enviad[oa]s?|mandaron|mandan|mandad[oa]s?) a (la )?(carcel|prision)|"
                                   r"\bcarcel para\b|\ba juicio\b|\bencan\w*")),
    ("condena", re.compile(r"\bconden|\bsentencia|\banos de (carcel|prision)|\bpagara\b|\bpagaran\b")),
    ("absolucion", re.compile(r"\babsuelt|\babsuelve|\babsolvi|\babsolucion|\bdejad[oa] en libertad")),
]
ORDEN_ESTADO = {"ND": 0, "denuncia": 1, "rescate": 2, "captura": 3, "judicializacion": 4,
                "condena": 5, "absolucion": 5}

MUERTE = re.compile(r"\basesinad|\bmurio\b|\bmuerte de|\bsin vida|\bhomicidio|\bfeminicidio|"
                    r"\bmuerta\b|\bmato\b|\bcadaver|\bcuerpo de (la|una) (nina|menor)|\bfallecio")


def estado(t):
    actual = "ND"
    for nombre, patron in ESTADOS:
        if patron.search(t):
            actual = nombre
    return actual


def muerte_victima(t):
    return bool(MUERTE.search(t))


# ----------------------------------------------------------------------------
# 6. Menciones del exterior
# ----------------------------------------------------------------------------
# No incluye lugares que tambien son municipios de Colombia (Madrid, Florida, Puerto Rico...)
EXTERIOR = re.compile(
    r"\b(argentina|mexico|peru|ecuador|espana|el salvador|chile|venezuela|estados unidos|ee\.? ?uu|"
    r"brasil|guatemala|honduras|panama|costa rica|bolivia|paraguay|uruguay|nicaragua|cuba|"
    r"republica dominicana|haiti|italia|francia|alemania|reino unido|inglaterra|canada|china|india|"
    r"japon|rusia|ucrania|gaza|israel|texas|california|nueva york|miami|barcelona|lima|quito|"
    r"caracas|buenos aires|ciudad de mexico|cdmx|jalisco|sinaloa|chihuahua|guayaquil|houston|"
    r"los angeles|tegucigalpa|san salvador|santo domingo|portugal|australia|filipinas|tailandia|"
    r"indonesia|pakistan|afganistan|iran|irak|siria|marruecos|nigeria|kenia|sudafrica|"
    # estados y provincias. NO incluye los que tambien son municipios de Colombia (Malaga),
    # apellidos/nombres comunes aqui (Mendoza, Murcia, Burgos, Oviedo, Orlando) ni palabras
    # del espanol (salta, nevada, sonora)
    r"tamaulipas|nuevo leon|coahuila|veracruz|puebla|oaxaca|michoacan|yucatan|"
    r"quintana roo|baja california|zacatecas|morelos|queretaro|tabasco|chiapas|aguascalientes|"
    r"nayarit|tlaxcala|campeche|guanajuato|estado de mexico|edomex|tucuman|jujuy|neuquen|chubut|"
    r"entre rios|mar del plata|bahia blanca|catamarca|santiago del estero|"
    r"conurbano|andalucia|cataluna|galicia|asturias|alicante|bilbao|ceuta|"
    r"melilla|canarias|baleares|mallorca|tenerife|navarra|pais vasco|euskadi|cadiz|"
    r"valladolid|vigo|gijon|girona|tarragona|almeria|huelva|badajoz|"
    r"antofagasta|temuco|iquique|arica|rancagua|arequipa|cusco|callao|chiclayo|piura|huancayo|"
    r"maracaibo|tachira|barquisimeto|maracay|san pedro sula|managua|chicago|arizona|"
    r"atlanta|boston|dallas|las vegas|phoenix|veraguas|chiriqui|bocas del toro|san miguelito|penonome|"
    r"suiza|corea|noruega|suecia|dinamarca|holanda|paises bajos|belgica|grecia|turquia|egipto|sudan|vietnam|"
    r"polonia|irlanda|escocia|\bice)\b")

# Instituciones y palabras propias de otros paises
VOCABULARIO_EXTERIOR = re.compile(
    r"\bguardia civil\b|\bmossos\b|\bertzaintza\b|\baudiencia (provincial|nacional|de \w+)\b|"
    r"\bpolicia local\b|\bcarabineros\b|\bremiser|\bfgr\b|\bfiscalia general de la republica\b|"
    r"\bescuadron violeta\b|\bministerio publico fiscal\b|\bpiso tutelado\b|\bjuzgado de instruccion\b|"
    r"\bpolicia de la ciudad\b|\bsspc\b|\bsscbc\b|\banep\b|\bformalizad[oa]s?\b|\bsename\b|\bdif\b")


def menciona_exterior(t):
    return bool(EXTERIOR.search(t) or VOCABULARIO_EXTERIOR.search(t))
