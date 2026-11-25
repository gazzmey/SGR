#!/usr/bin/env python3
"""
Prueba de carga y estrés del SGR (protocolo B18 del plan de pruebas).

Solo usa la biblioteca estándar de Python 3.8+: se puede correr desde el
servidor de QA, desde un computador del equipo o contra AWS sin instalar nada.

Cada usuario virtual inicia sesión con su propia cuenta y repite, con una
pausa de 0,5 a 1,5 s entre acciones, una mezcla de operaciones:

    consulta/filtro 50 %   ficha/tablero 20 %   registro 20 %   validación 10 %

La validación la hacen los usuarios virtuales con cuenta de verificador (uno
de cada diez); el resto reparte su tiempo entre las otras tres en la misma
proporción. Cada registro lleva un texto único, así que al terminar se puede
conciliar contra la base: cuántos se pidieron, cuántos respondieron bien y
cuántos quedaron guardados. Un registro que responde error se reenvía una
vez con la misma ficha de envío, como haría una persona; la ficha impide que
ese reenvío lo duplique (DEF-10). Con --sin-reintento no se reenvía.

Ejemplo (QA local):
    SGR_CARGA_CLAVE=... python3 carga_sgr.py --base http://127.0.0.1:8771 \\
        --etapas control:1:30,normal:10:60,carga20:20:45,carga50:50:45,estres:100:45,recuperacion:1:30

Contra AWS, sin escribir en la base (solo consultas, fichas y tableros) y con
las cuentas de demostración:
    SGR_CARGA_CLAVE=... python3 carga_sgr.py --base http://<servidor> --solo-lectura \
        --cuentas marcela.rios@ejemplo.cl,camila.otarola@ejemplo.cl,jorge.salinas@ejemplo.cl,hector.pizarro@ejemplo.cl \
        --etapas control:1:120,normal:10:600,carga20:20:300

La contraseña se lee de una variable de entorno: no se escribe en la línea
de comandos ni queda en los resultados.
"""
import argparse
import csv
import http.cookiejar
import json
import os
import random
import re
import statistics
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

PESOS_FUNCIONARIO = [("consulta", 50), ("ficha", 20), ("registro", 20)]


class SinRedireccion(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


class Sesion:
    def __init__(self, base, timeout=30):
        self.base = base.rstrip("/")
        self.jar = http.cookiejar.CookieJar()
        self.abre = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar), SinRedireccion())
        self.timeout = timeout

    def token(self):
        return next((c.value for c in self.jar if c.name == "csrftoken"), "")

    def pedir(self, ruta, datos=None):
        url = self.base + ruta
        cuerpo = None
        cab = {"User-Agent": "carga-sgr/1.0"}
        if datos is not None:
            datos = dict(datos, csrfmiddlewaretoken=self.token())
            cuerpo = urllib.parse.urlencode(datos).encode()
            cab["Referer"] = url
        inicio = time.perf_counter()
        try:
            r = self.abre.open(urllib.request.Request(url, data=cuerpo, headers=cab), timeout=self.timeout)
            estado, texto = r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            estado, texto = e.code, e.read().decode("utf-8", "replace") if e.fp else ""
        except Exception as e:  # tiempo agotado, conexión rechazada
            return 0, f"{type(e).__name__}: {e}", (time.perf_counter() - inicio) * 1000
        return estado, texto, (time.perf_counter() - inicio) * 1000

    def entrar(self, correo, clave):
        self.pedir("/cuenta/ingresar/")
        estado, _, _ = self.pedir("/cuenta/ingresar/", {"username": correo, "password": clave})
        return estado == 302


class Prueba:
    def __init__(self, args):
        self.a = args
        self.clave = os.environ[args.clave_env]
        self.muestras = []
        self.registros_pedidos = []
        self.reintentos = 0
        self.cerrojo = threading.Lock()
        self.corrida = time.strftime("%H%M%S")

    def anotar(self, etapa, op, estado, ms, ok):
        with self.cerrojo:
            self.muestras.append({"t": time.time(), "etapa": etapa, "op": op, "estado": estado, "ms": round(ms, 1), "ok": ok})

    def usuario(self, etapa, n, hasta):
        es_verif = (n % 10 == 9) and not self.a.solo_lectura
        if self.a.cuentas:
            lista = [x.strip() for x in self.a.cuentas.split(",") if x.strip()]
            correo = lista[n % len(lista)]
            es_verif = False
        else:
            correo = (self.a.verificador % (n // 10 % self.a.n_verificadores + 1)) if es_verif \
                else (self.a.funcionario % (n % self.a.n_funcionarios + 1))
        s = Sesion(self.a.base)
        inicio = time.perf_counter()
        ok = s.entrar(correo, self.clave)
        self.anotar(etapa, "ingreso", 302 if ok else 0, (time.perf_counter() - inicio) * 1000, ok)
        if not ok:
            return
        item = None
        if not es_verif:
            _, html, _ = s.pedir("/periodo/actividades/nueva/")
            m = re.search(r'<select[^>]*name="item"[^>]*>(.*?)</select>', html, re.S)
            opciones = re.findall(r'<option value="(\d+)"', m.group(1)) if m else []
            item = opciones[0] if opciones else None
        k = 0
        while time.time() < hasta:
            k += 1
            if es_verif:
                op = "validacion"
            else:
                pesos = [(o, w) for o, w in PESOS_FUNCIONARIO if not (self.a.solo_lectura and o == "registro")]
                op = random.choices([o for o, _ in pesos], [w for _, w in pesos])[0]
            if op == "consulta":
                ruta = random.choice(["/periodo/actividades/",
                                      "/periodo/agenda/?situacion=todos&q=%s" % random.choice(["luz", "junta", "CMP", "plaza", ""]),
                                      "/periodo/actividades/?q=carga"])
                estado, html, ms = s.pedir(ruta)
                self.anotar(etapa, op, estado, ms, estado == 200)
            elif op == "ficha":
                estado, html, ms = s.pedir(random.choice(["/periodo/mi-resultado/", "/"]))
                self.anotar(etapa, op, estado, ms, estado == 200)
            elif op == "registro" and item:
                # Como una persona: abre el formulario (que trae su ficha de
                # envío) y lo guarda. Si la respuesta es un error, vuelve a
                # enviar el MISMO formulario una vez; con la ficha, ese
                # reenvío no puede duplicar la actividad (DEF-10).
                texto = f"Carga {self.corrida} {etapa} VU{n} #{k}"
                _, html, _ = s.pedir("/periodo/actividades/nueva/")
                m = re.search(r'name="envio" value="([^"]*)"', html)
                datos = {"item": item, "fecha": time.strftime("%Y-%m-%d"), "cantidad": "1", "tipo": "terreno",
                         "origen": "planificada", "accion": texto,
                         "detalle": "Registro de la prueba de carga con datos ficticios.",
                         "envio": m.group(1) if m else ""}
                estado, html, ms = s.pedir("/periodo/actividades/nueva/", datos)
                self.anotar(etapa, op, estado, ms, estado == 302)
                if estado != 302 and not self.a.sin_reintento:
                    time.sleep(random.uniform(0.5, 1.5))
                    estado, html, ms = s.pedir("/periodo/actividades/nueva/", datos)
                    self.anotar(etapa, "registro_reintento", estado, ms, estado == 302)
                    with self.cerrojo:
                        self.reintentos += 1
                with self.cerrojo:
                    self.registros_pedidos.append((texto, estado))
            elif op == "validacion":
                estado, html, ms = s.pedir("/periodo/validar/?p=%d" % random.randint(1, 3))
                self.anotar(etapa, "cola_validacion", estado, ms, estado == 200)
                pks = re.findall(r'href="/periodo/validar/(\d+)/"', html)
                if pks:
                    pk = random.choice(pks)
                    estado, _, ms = s.pedir(f"/periodo/validar/{pk}/aprobar/", {})
                    self.anotar(etapa, op, estado, ms, estado == 302)
            time.sleep(random.uniform(0.5, 1.5))

    def etapa(self, nombre, usuarios, segundos):
        hasta = time.time() + segundos
        hilos = []
        for n in range(usuarios):
            h = threading.Thread(target=self.usuario, args=(nombre, n, hasta), daemon=True)
            hilos.append(h)
            h.start()
            time.sleep(min(0.2, segundos / max(usuarios, 1) / 4))   # subida gradual
        for h in hilos:
            h.join(timeout=segundos + 60)

    def resumen(self):
        filas = []
        etapas = []
        for m in self.muestras:
            if m["etapa"] not in etapas:
                etapas.append(m["etapa"])
        for et in etapas:
            ms_et = [m for m in self.muestras if m["etapa"] == et]
            dur = (max(m["t"] for m in ms_et) - min(m["t"] for m in ms_et)) or 1
            for op in sorted({m["op"] for m in ms_et}) + ["TODAS"]:
                g = [m for m in ms_et if op == "TODAS" or m["op"] == op]
                lat = sorted(m["ms"] for m in g)
                if not lat:
                    continue
                def pct(q):
                    return lat[min(len(lat) - 1, int(round(q / 100 * (len(lat) - 1))))]
                errores = sum(1 for m in g if not m["ok"])
                filas.append({"etapa": et, "operacion": op, "solicitudes": len(g), "por_segundo": round(len(g) / dur, 2),
                              "promedio_ms": round(statistics.mean(lat), 1), "p50_ms": pct(50), "p95_ms": pct(95), "p99_ms": pct(99),
                              "max_ms": lat[-1], "errores": errores, "errores_pct": round(errores * 100 / len(g), 2)})
        return filas


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", required=True)
    ap.add_argument("--etapas", default="control:1:30,normal:10:60")
    ap.add_argument("--funcionario", default="perf.f%02d@ejemplo.cl")
    ap.add_argument("--n-funcionarios", type=int, default=40)
    ap.add_argument("--verificador", default="perf.v%d@ejemplo.cl")
    ap.add_argument("--n-verificadores", type=int, default=4)
    ap.add_argument("--clave-env", default="SGR_CARGA_CLAVE")
    ap.add_argument("--cuentas", default="", help="correos separados por coma; reemplaza a --funcionario")
    ap.add_argument("--solo-lectura", action="store_true", help="sin registros ni validaciones: no escribe en la base")
    ap.add_argument("--sin-reintento", action="store_true",
                    help="no reenviar un registro que respondió error (comportamiento anterior a DEF-10)")
    ap.add_argument("--salida", default="resultados_carga")
    a = ap.parse_args()
    os.makedirs(a.salida, exist_ok=True)
    prueba = Prueba(a)
    for tramo in a.etapas.split(","):
        nombre, usuarios, segundos = tramo.split(":")
        print(f"→ {nombre}: {usuarios} usuarios durante {segundos} s", flush=True)
        prueba.etapa(nombre, int(usuarios), int(segundos))
    res = prueba.resumen()
    with open(os.path.join(a.salida, "muestras.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["t", "etapa", "op", "estado", "ms", "ok"])
        w.writeheader(); w.writerows(prueba.muestras)
    with open(os.path.join(a.salida, "resumen.json"), "w") as f:
        json.dump({"base": a.base, "etapas": a.etapas, "corrida": prueba.corrida, "resumen": res,
                   "registros_pedidos": len(prueba.registros_pedidos),
                   "registros_ok": sum(1 for _, e in prueba.registros_pedidos if e == 302),
                   "reintentos": prueba.reintentos,
                   "textos_registro": [t for t, e in prueba.registros_pedidos if e == 302]}, f, ensure_ascii=False, indent=1)
    for r in res:
        if r["operacion"] == "TODAS":
            print(f"{r['etapa']:>13}: {r['solicitudes']:5d} sol. {r['por_segundo']:6.2f}/s  prom {r['promedio_ms']:7.1f} ms  "
                  f"p95 {r['p95_ms']:7.1f}  p99 {r['p99_ms']:7.1f}  máx {r['max_ms']:7.1f}  errores {r['errores_pct']} %")


if __name__ == "__main__":
    main()
