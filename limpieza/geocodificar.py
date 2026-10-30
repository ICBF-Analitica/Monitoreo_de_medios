# -*- coding: utf-8 -*-
"""
geocodificar.py - Ubica cada noticia en un municipio de Colombia usando DIVIPOLA (DANE).

Estilo ACLED, devuelve un nivel de precision:
  1 = municipio identificado
  2 = solo departamento (se usan las coordenadas de su capital)
  3 = sin ubicacion en Colombia (o municipio ambiguo)

Reglas para no confundir lugares (ver CODEBOOK.md, seccion 6):
  - Capitales y ciudades grandes se aceptan si aparecen con mayuscula.
  - Municipios pequenos solo se aceptan con contexto: "en X", "municipio de X" o "X, Departamento".
  - Nombres que tambien son palabras comunes, apellidos o lugares del exterior
    (Jardin, Soledad, Caceres, Granada, Madrid...) exigen contexto Y mayuscula real.
  - Si un nombre existe en varios departamentos (66 casos), se desambigua con el
    departamento mencionado en la nota.
"""

import re
import pandas as pd
from .reglas import norm, menciona_exterior

TOKEN_RE = re.compile(r"\w+")
CONECTORES = {"de", "del", "la", "las", "el", "los", "y", "e"}
PREPOSICIONES = {"en", "de", "del", "desde", "hacia", "a", "al", "municipio", "corregimiento",
                 "vereda", "barrio", "sector", "zona", "ciudad", "pueblo", "departamento"}

# Nombre como lo escriben los medios -> nombre oficial en DIVIPOLA
ALIAS_MUNICIPIO = {
    "bogota": "BOGOTÁ, D.C.",
    "cartagena": "CARTAGENA DE INDIAS",
    "cucuta": "SAN JOSÉ DE CÚCUTA",
    "tumaco": "SAN ANDRÉS DE TUMACO",
    "mompox": "SANTA CRUZ DE MOMPOX",
    "mompos": "SANTA CRUZ DE MOMPOX",
    "mariquita": "SAN SEBASTIÁN DE MARIQUITA",
    "ubate": "VILLA DE SAN DIEGO DE UBATÉ",
    "tolu": "SANTIAGO DE TOLÚ",
    "san juan de pasto": "PASTO",
    "cali": "SANTIAGO DE CALI",
    "buga": "GUADALAJARA DE BUGA",
}
# Nombres repetidos sin capital entre los candidatos: cual elegir si la nota no dice el departamento
PREFERIDO = {"rionegro": "05615"}
# Solo se aceptan si van seguidos del departamento ("Colombia, Huila")
REQUIERE_DEPTO = {"colombia"}
ALIAS_DEPTO = {
    "valle": "VALLE DEL CAUCA",
    "guajira": "LA GUAJIRA",
    "san andres y providencia": "ARCHIPIÉLAGO DE SAN ANDRÉS, PROVIDENCIA Y SANTA CATALINA",
    "archipielago de san andres": "ARCHIPIÉLAGO DE SAN ANDRÉS, PROVIDENCIA Y SANTA CATALINA",
    "valle de aburra": "ANTIOQUIA",
}

# Ciudades grandes (ademas de las capitales) que se aceptan sin contexto
GRANDES = {
    "soacha", "itagui", "envigado", "palmira", "buenaventura", "tulua", "barrancabermeja",
    "floridablanca", "giron", "piedecuesta", "dosquebradas", "malambo", "facatativa", "zipaquira",
    "fusagasuga", "chia", "funza", "apartado", "san andres de tumaco", "maicao", "uribia", "ipiales",
    "sogamoso", "duitama", "girardot", "jamundi", "yumbo", "rionegro", "caucasia", "magangue",
    "lorica", "sahagun", "cienaga", "aguachica", "ocana", "pamplona", "villa del rosario",
    "los patios", "sabaneta", "copacabana", "girardota", "marinilla", "turbaco", "el carmen de bolivar",
    "fundacion", "plato", "espinal", "melgar", "chiquinquira", "pitalito", "la dorada", "calarca",
    "santander de quilichao", "tierralta", "montelibano", "planeta rica", "cerete", "puerto asis",
    "acacias", "aguazul", "tame", "saravena", "fonseca", "candelaria", "cajica", "tocancipa",
    "la ceja", "carepa", "chigorodo", "necocli", "arjona", "baranoa", "sabanalarga", "zarzal",
    "sevilla", "el cerrito", "pradera", "florida", "guadalajara de buga", "cartago",
}

# Tambien son palabras comunes, nombres/apellidos o lugares del exterior: regla estricta
COMUNES = {
    # palabras comunes
    "une", "turbo", "toro", "gama", "tena", "tota", "pore", "cota", "silos", "belen", "concordia",
    "victoria", "la victoria", "florida", "bello", "la union", "la esperanza", "primavera",
    "providencia", "el retiro", "dolores", "pueblo nuevo", "nuevo colon", "colon", "el carmen",
    "la paz", "guadalupe", "la plata", "el paso", "la vega", "la mesa", "la pena", "el cerrito",
    "la playa", "la estrella", "andes", "el penol", "jardin", "remedios", "campamento", "pesca",
    "toca", "calamar", "pajarito", "soledad", "manati", "arenal", "floresta", "corrales",
    "la capilla", "el espino", "guacamayas", "cienega", "peque", "pradera", "fresno", "la ceja",
    "palmar", "buenavista", "villanueva", "sabanalarga", "candelaria", "plato", "fundacion",
    "el bagre", "la merced", "maceo", "montecristo", "santuario", "el santuario", "la sierra",
    "el tambo", "la cruz", "el rosal", "puerto colombia",
    # nombres y apellidos
    "barbosa", "ortega", "ospina", "caicedo", "herran", "olaya", "ricaurte", "mosquera",
    "lebrija", "garzon", "florian", "gomez plata", "murillo", "pacho", "ulloa", "caceres",
    "carolina", "valdivia", "briceno", "giraldo", "arjona", "clemencia", "pinillos", "margarita",
    "morales", "zambrano", "santana", "paez", "rondon", "almeida", "salgar", "neira", "gamarra",
    "juan de acosta", "regidor", "anza", "rivera", "san fernando", "san mateo", "san pablo", "san pedro",
    "san juan", "san luis", "san carlos", "san jose", "san miguel", "san martin", "san vicente",
    "san antonio", "san rafael", "santa rosa", "santa ana", "santa maria", "santa lucia",
    "santa catalina", "santa isabel", "santa sofia", "santa barbara", "san francisco", "santiago",
    "narino", "caldas", "sucre", "bolivar", "cordoba", "albania", "granada",
    # lugares del exterior
    "venecia", "genova", "palermo", "armenia", "palestina", "el libano", "argelia", "montenegro",
    "madrid", "sevilla", "valencia", "toledo", "puerto rico", "cartago", "jerico", "salento",
    "betania", "filadelfia", "roncesvalles", "cajamarca", "trujillo", "segovia", "zaragoza",
    "amalfi", "hispania", "tamesis", "valparaiso", "miraflores", "aquitania", "san cristobal",
    "copacabana", "california",
}
# Si la nota habla del exterior, estos nombres no se toman como Colombia
COLISION_EXTRANJERA = {
    "madrid", "granada", "cordoba", "sevilla", "valencia", "toledo", "santiago", "florencia",
    "venecia", "genova", "palermo", "armenia", "albania", "palestina", "el libano", "argelia",
    "montenegro", "puerto rico", "florida", "la paz", "cartago", "jerico", "belen", "filadelfia",
    "trujillo", "cajamarca", "victoria", "la victoria", "guadalupe", "la union", "san miguel",
    "santa ana", "san jose", "santa fe", "colon", "segovia", "zaragoza", "amalfi", "valparaiso",
    "miraflores", "san cristobal", "santander", "bolivar", "amazonas", "sucre", "copacabana",
    "california", "rivera", "el zulia", "lerida",
}
# Departamentos cuyo nombre tambien es palabra comun: exigen "en/del/de ..." delante
DEPTOS_COMUNES = {"meta", "valle", "cesar", "magdalena", "santander", "atlantico", "amazonas",
                  "cordoba", "bolivar", "sucre", "caldas", "narino", "choco"}


def _clave(texto):
    """Normaliza un nombre oficial para buscarlo: sin tildes, sin signos."""
    return " ".join(TOKEN_RE.findall(norm(texto)))


class Geocodificador:
    def __init__(self, ruta_divipola):
        d = pd.read_csv(ruta_divipola, dtype=str)
        d["lat"] = d["latitud"].str.replace(",", ".").astype(float)
        d["lon"] = d["longitud"].str.replace(",", ".").astype(float)
        self.mpios = d.set_index("cod_mpio")

        # municipio: clave normalizada -> lista de codigos DIVIPOLA
        self.idx_mpio = {}
        for cod, nombre in d[["cod_mpio", "nom_mpio"]].values:
            self.idx_mpio.setdefault(_clave(nombre), []).append(cod)
        for alias, oficial in ALIAS_MUNICIPIO.items():
            self.idx_mpio.setdefault(alias, []).extend(d.loc[d.nom_mpio == oficial, "cod_mpio"])
        self.idx_mpio = {k: list(dict.fromkeys(v)) for k, v in self.idx_mpio.items()}

        # departamento: clave normalizada -> codigo (Bogota se trata como municipio)
        deptos = d.drop_duplicates("cod_dpto")
        self.nom_dpto = dict(zip(deptos.cod_dpto, deptos.dpto))
        self.idx_dpto = {_clave(n): c for c, n in self.nom_dpto.items() if c != "11"}
        for alias, oficial in ALIAS_DEPTO.items():
            self.idx_dpto[alias] = next(c for c, n in self.nom_dpto.items() if n == oficial)

        # capital de cada departamento (coordenadas para precision 2)
        self.capital = {}
        for cod in self.nom_dpto:
            cap = "11001" if cod in ("11", "25") else cod + "001"
            if cap not in self.mpios.index:
                cap = self.mpios[self.mpios.cod_dpto == cod].index[0]
            self.capital[cod] = cap
        self.capitales = set(self.capital.values())
        self.grandes = GRANDES | {_clave(self.mpios.loc[c, "nom_mpio"]) for c in self.capitales} | set(ALIAS_MUNICIPIO)
        self.cod_grandes = {c for k in self.grandes for c in self.idx_mpio.get(k, [])}
        self.max_n = max(len(k.split()) for k in list(self.idx_mpio) + list(self.idx_dpto))

    # ------------------------------------------------------------------------
    def ubicar(self, titulo):
        orig = TOKEN_RE.findall(str(titulo))
        toks = [norm(x) for x in orig]
        exterior = menciona_exterior(" ".join(toks))
        largas = [o for o in orig if len(o) > 3 and o.isalpha()]
        # en titulos "Con Mayuscula Inicial" la mayuscula no sirve como senal
        titulo_case = bool(largas) and sum(o[0].isupper() for o in largas) / len(largas) > 0.6

        # 1. Buscar nombres de lugares (la coincidencia mas larga primero)
        hallazgos = []  # (inicio, fin, clave, es_municipio, es_departamento)
        i = 0
        while i < len(toks):
            for n in range(min(self.max_n, len(toks) - i), 0, -1):
                clave = " ".join(toks[i:i + n])
                if clave in self.idx_mpio or clave in self.idx_dpto:
                    hallazgos.append((i, i + n, clave, clave in self.idx_mpio, clave in self.idx_dpto))
                    i += n
                    break
            else:
                i += 1

        def mayuscula(ini, fin):
            palabras = [orig[k] for k in range(ini, fin) if toks[k] not in CONECTORES]
            return all(p[0].isupper() for p in palabras)

        def prep_antes(ini):
            return ini > 0 and toks[ini - 1] in PREPOSICIONES

        def depto_despues(fin):
            for ini2, _, clave2, _, es_d2 in hallazgos:
                if ini2 == fin and es_d2:
                    return self.idx_dpto[clave2]
            return None

        # 2. Departamentos mencionados (sirven para desambiguar y para precision 2)
        deptos = []  # (codigo, es_seguro)
        for ini, fin, clave, es_m, es_d in hallazgos:
            if not es_d or not (mayuscula(ini, fin) or titulo_case):
                continue
            despues_de_mpio = any(f2 == ini and m2 for _, f2, _, m2, _ in hallazgos)
            if clave in DEPTOS_COMUNES and not (prep_antes(ini) or despues_de_mpio):
                continue
            if clave in COLISION_EXTRANJERA and exterior:
                continue
            seguro = despues_de_mpio or not (clave in DEPTOS_COMUNES or clave in COLISION_EXTRANJERA)
            colision = clave in COLISION_EXTRANJERA and not despues_de_mpio
            deptos.append((self.idx_dpto[clave], seguro, colision))
        cods_depto = [c for c, _, _ in deptos]

        # 3. Municipios
        candidatos = []  # (lista de codigos, precedido por "en", es_seguro)
        for ini, fin, clave, es_m, es_d in hallazgos:
            if not es_m:
                continue
            d_sig = depto_despues(fin)
            # "Bolivar", "Sucre"... solos se toman como departamento
            if es_d and d_sig is None and not (ini > 0 and toks[ini - 1] == "municipio"):
                continue
            if clave == "jardin" and fin < len(toks) and toks[fin] in ("infantil", "de", "escolar"):
                continue
            if clave in REQUIERE_DEPTO and d_sig is None:
                continue
            cap = mayuscula(ini, fin)
            if clave in COMUNES:
                ok = d_sig is not None or (prep_antes(ini) and cap and not titulo_case)
            elif clave in self.grandes:
                ok = cap or titulo_case
            else:
                ok = (cap or titulo_case) and (prep_antes(ini) or d_sig is not None)
            if not ok or (clave in COLISION_EXTRANJERA and exterior and d_sig is None):
                continue

            cods = self.idx_mpio[clave]
            if len(cods) > 1:  # desambiguar con el departamento
                pistas = [d_sig] if d_sig else cods_depto
                en_depto = [c for c in cods if self.mpios.loc[c, "cod_dpto"] in pistas]
                capitales = [c for c in cods if c in self.capitales]
                if len(en_depto) == 1:
                    cods = en_depto
                elif len(capitales) == 1:
                    cods = capitales
                elif clave in PREFERIDO and not pistas:
                    cods = [PREFERIDO[clave]]
            # seguro = no se puede confundir con otro lugar (ciudad grande inequivoca, o "X, Depto")
            seguro = d_sig is not None or (clave in self.grandes and clave not in COMUNES
                                           and clave not in COLISION_EXTRANJERA)
            # riesgo de que sea un lugar del exterior con el mismo nombre (Cordoba, Valencia...)
            colision = clave in COLISION_EXTRANJERA and d_sig is None
            candidatos.append((cods, ini > 0 and toks[ini - 1] == "en", seguro, colision))

        # 4. Elegir: municipio resuelto (preferir el que va despues de "en") > departamento > nada
        resueltos = [(c[0], en, seg, col) for c, en, seg, col in candidatos if len(c) == 1]
        if resueltos:
            cod, _, seguro, colision = next((r for r in resueltos if r[1]), resueltos[0])
            return self._resultado(cod, 1, seguro, colision)
        if deptos:
            cod_d, seguro, colision = deptos[0]
            return self._resultado(self.capital[cod_d], 2, seguro, colision, cod_dpto=cod_d)
        ambiguos = [c for c, _, _, _ in candidatos]
        # "Toledo" (2 municipios en Colombia) tambien es una ciudad de Espana: sin apoyo del medio no se asume Colombia
        cand_colision = bool(ambiguos) and all(col for _, _, _, col in candidatos)
        return {"candidatos_colision": cand_colision, "municipio": "", "cod_divipola": "", "departamento": "", "cod_dpto": "",
                "geo_precision": 3, "lat": None, "lon": None, "ubic_segura": False,
                "riesgo_colision": False, "mpio_grande": False,
                "ambito": "colombia" if ambiguos else ("exterior" if exterior else "ND"),
                "texto_exterior": exterior,
                "candidatos": " / ".join(self._nombre(x) for c in ambiguos for x in c)}

    # ------------------------------------------------------------------------
    def _nombre(self, cod):
        f = self.mpios.loc[cod]
        return f"{f.nom_mpio} ({f.dpto})"

    def _resultado(self, cod, precision, seguro, colision, cod_dpto=None):
        """En precision 2, `cod` es la capital (solo para las coordenadas) y `cod_dpto` el
        departamento real: la capital de Cundinamarca es Bogota, que es otro departamento."""
        f = self.mpios.loc[cod]
        cod_dpto = cod_dpto or f.cod_dpto
        return {"municipio": f.nom_mpio if precision == 1 else "",
                "cod_divipola": cod if precision == 1 else "",
                "departamento": self.nom_dpto[cod_dpto], "cod_dpto": cod_dpto, "geo_precision": precision,
                "lat": f.lat, "lon": f.lon, "ubic_segura": bool(seguro),
                "riesgo_colision": bool(colision),
                # en una ciudad grande coincidir en el municipio no prueba que sea el mismo caso
                "mpio_grande": precision == 1 and cod in self.cod_grandes, "ambito": "colombia",
                "texto_exterior": False, "candidatos": ""}
