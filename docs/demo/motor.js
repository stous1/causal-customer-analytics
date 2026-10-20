/*
 * Cálculos de la página interactiva, sin acceso al DOM. Funciona en el navegador (window.Motor)
 * y en Node (module.exports), para que tests/test_demo.py compare con Python.
 */
(function (raiz, fabrica) {
  if (typeof module === "object" && module.exports) {
    module.exports = fabrica();
  } else {
    raiz.Motor = fabrica();
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  /** Número con coma decimal, como en el resto del proyecto. */
  function coma(x, d) {
    var s = Math.abs(x).toFixed(d).replace(".", ",");
    return (x < 0 && Number(Math.abs(x).toFixed(d)) !== 0 ? "−" : "") + s;
  }

  /** Con signo explícito: +0,089 / −0,038. */
  function conSigno(x, d) {
    return (x > 0 ? "+" : "") + coma(x, d);
  }

  /** Puntos porcentuales: 0,0889 -> "+8,9 pp". */
  function pp(x, d) {
    return conSigno(x * 100, d === undefined ? 1 : d) + " pp";
  }

  function miles(n) {
    return String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  }

  /**
   * Valor neto por cliente de una estrategia en la mitad de prueba de Hillstrom:
   * suma por celda de w_k * (visitas/clientes del brazo elegido - costo si se envía correo).
   * Misma fórmula que causal.demo.valor.
   */
  function valorPolitica(celdas, asignacion, costo) {
    var total = 0;
    celdas.forEach(function (c) { total += c.clientes_prueba; });
    var v = 0, varianza = 0, enviados = 0;
    celdas.forEach(function (c, i) {
      var a = asignacion[i];
      var w = c.clientes_prueba / total;
      var b = c.brazos[a];
      var p = b.visitas / b.clientes;
      v += w * (p - (a > 0 ? costo : 0));
      varianza += w * w * p * (1 - p) / b.clientes;
      if (a > 0) enviados += w;
    });
    return { valor: v, ee: Math.sqrt(varianza), fraccionConCorreo: enviados };
  }

  /** Efecto del brazo (1 hombre, 2 mujer) frente a sin correo dentro de una celda. */
  function efectoCelda(celda, brazo) {
    var t = celda.brazos[brazo], c = celda.brazos[0];
    var p1 = t.visitas / t.clientes, p0 = c.visitas / c.clientes;
    var ee = Math.sqrt(p1 * (1 - p1) / t.clientes + p0 * (1 - p0) / c.clientes);
    return { efecto: p1 - p0, ee: ee };
  }

  /** La mejor acción por celda para un costo dado (mirando la prueba: solo ilustrativo). */
  function mejorPorCelda(celdas, costo) {
    return celdas.map(function (c) {
      var mejor = 0, valorMejor = -Infinity;
      for (var a = 0; a < 3; a++) {
        var v = c.brazos[a].visitas / c.brazos[a].clientes - (a > 0 ? costo : 0);
        if (v > valorMejor) { valorMejor = v; mejor = a; }
      }
      return mejor;
    });
  }

  /** Qué fracción del efecto estimado ya aparece en el placebo de adelanto. */
  function fraccionPlacebo(analisis) {
    if (!analisis.placebo_adelanto) return null;
    return analisis.placebo_adelanto.efecto / analisis.efecto;
  }

  return {
    coma: coma,
    conSigno: conSigno,
    pp: pp,
    miles: miles,
    valorPolitica: valorPolitica,
    efectoCelda: efectoCelda,
    mejorPorCelda: mejorPorCelda,
    fraccionPlacebo: fraccionPlacebo
  };
});
