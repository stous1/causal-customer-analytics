/* Página "¿Predice o causa?": lee los JSON publicados y arma las dos pestañas. */
(function () {
  "use strict";
  var M = window.Motor;
  var R = "resultados/";

  var PREGUNTAS = [
    {
      id: "nomina_actividad",
      chip: "Nómina",
      titulo: "¿Traer la nómina vuelve más activo al cliente?",
      predice: "nomina",
      prediceSub: "Qué variables usa el modelo del hito 2 para anticipar que un cliente empiece a recibir la nómina el mes siguiente.",
      lecturaPredice: "La actividad y la relación activa del cliente son lo que más anticipa que traiga la nómina: la flecha que el modelo ve va de la actividad a la nómina.",
      animacion: true
    },
    {
      id: "canal_meses_activo",
      chip: "Canal de vinculación",
      titulo: "¿Entrar por el canal KHM (frente a KHN) cambia cuánto tiempo sigue activo?",
      predice: null,
      lecturaPredice: "El canal se fija al entrar: aquí no hay nada que predecir mes a mes. Es la única pregunta donde la parte causal pasa todas las pruebas aplicables (aunque no admite placebo de adelanto)."
    },
    {
      id: "producto_tjcr",
      chip: "Tarjeta de crédito",
      titulo: "¿Adquirir una tarjeta de crédito frena el paso de activo a inactivo?",
      predice: "tjcr",
      prediceSub: "Qué variables usa el modelo del hito 2 para anticipar que un cliente adquiera la tarjeta el mes siguiente.",
      lecturaPredice: "La relación activa y la actividad predicen la adquisición. Eso no dice que la tarjeta retenga."
    },
    {
      id: "producto_ecue",
      chip: "Cuenta electrónica",
      titulo: "¿Adquirir una cuenta electrónica frena el paso de activo a inactivo?",
      predice: "ecue",
      prediceSub: "Qué variables usa el modelo del hito 2 para anticipar que un cliente adquiera la cuenta electrónica.",
      lecturaPredice: "Ser activo es lo que más predice la adquisición. La pregunta causal es la inversa: ¿adquirirla lo mantiene activo?"
    },
    {
      id: "producto_recibo",
      chip: "Débito automático",
      titulo: "¿Domiciliar un débito automático frena el paso de activo a inactivo?",
      predice: "recibo",
      prediceSub: "Qué variables usa el modelo del hito 2 para anticipar que un cliente domicilie un débito.",
      lecturaPredice: "Otra vez, la actividad del cliente es lo que más predice la adquisición."
    }
  ];

  var NOMBRES_PRUEBAS = {
    significativo: "El intervalo de 95 % excluye el cero",
    placebo_adelanto: "Placebo de adelanto: quienes se tratarán en 4 meses no difieren antes",
    consistencia: "Emparejamiento, Double ML y bosque causal coinciden",
    placebo_permutacion: "DoWhy: con el tratamiento permutado el efecto desaparece",
    causa_comun_aleatoria: "DoWhy: una covariable aleatoria no lo mueve",
    subconjunto: "DoWhy: estable en subconjuntos del 80 %",
    sensibilidad_robusto: "Un confusor omitido tendría que ser más fuerte que cualquier covariable observada"
  };
  var NOMBRES_METODOS = {
    ingenuo: "Ingenuo (sin ajuste)",
    regresion: "Regresión lineal",
    emparejamiento: "Emparejamiento",
    dml_att: "Double ML (principal)",
    did_dr: "Dif. en dif.",
    bosque_causal: "Bosque causal"
  };

  function el(html) {
    var t = document.createElement("template");
    t.innerHTML = html.trim();
    return t.content.firstElementChild;
  }

  function claseVeredicto(v) {
    if (v === "creíble") return "v-creible";
    if (v === "creíble pero sensible") return "v-sensible";
    if (v === "no separable de la selección") return "v-seleccion";
    if (v === "sin efecto detectable") return "v-nada";
    return "v-fragil";
  }

  function unidad(id) {
    if (id === "canal_meses_activo") return { f: function (x) { return M.conSigno(x, 2) + " meses"; }, nombre: "meses activo (de 6)" };
    return { f: function (x) { return M.pp(x, 1); }, nombre: "puntos porcentuales" };
  }

  /* ---------- pestaña 1 ---------- */

  function barrasShap(shap) {
    var vars = shap.variables.slice(0, 6);
    var max = vars[0].shap_medio_abs;
    return '<ul class="barras">' + vars.map(function (v) {
      return '<li><span class="etiqueta">' + v.nombre + '</span><span class="pista"><span class="relleno" style="width:' +
        (100 * v.shap_medio_abs / max).toFixed(1) + '%; display:block"></span></span></li>';
    }).join("") + "</ul>";
  }

  function bosque(a, u) {
    var filas = Object.keys(a.metodos).map(function (k) {
      return { nombre: NOMBRES_METODOS[k] || k, e: a.metodos[k].efecto, lo: a.metodos[k].ic95[0], hi: a.metodos[k].ic95[1], pl: false };
    });
    if (a.placebo_adelanto) {
      filas.push({ nombre: "Placebo de adelanto", e: a.placebo_adelanto.efecto, lo: a.placebo_adelanto.ic95[0], hi: a.placebo_adelanto.ic95[1], pl: true });
    }
    var vals = [0];
    filas.forEach(function (f) { vals.push(f.lo, f.hi); });
    var mn = Math.min.apply(null, vals), mx = Math.max.apply(null, vals);
    var pad = (mx - mn) * 0.08 || 0.01;
    mn -= pad; mx += pad;
    var W = 560, izq = 190, der = 20, alto = 26 * filas.length + 30;
    function x(v) { return izq + (v - mn) / (mx - mn) * (W - izq - der); }
    var s = '<svg class="figura" viewBox="0 0 ' + W + " " + alto + '" role="img" aria-label="Efecto por método">';
    s += '<line class="eje" x1="' + x(0) + '" x2="' + x(0) + '" y1="4" y2="' + (alto - 22) + '"/>';
    filas.forEach(function (f, i) {
      var y = 18 + i * 26, cl = f.pl ? " placebo" : "";
      s += '<text x="0" y="' + (y + 4) + '">' + f.nombre + "</text>";
      s += '<line class="rango' + cl + '" x1="' + x(f.lo) + '" x2="' + x(f.hi) + '" y1="' + y + '" y2="' + y + '"/>';
      s += '<circle class="punto' + cl + '" cx="' + x(f.e) + '" cy="' + y + '" r="5"/>';
    });
    s += '<text class="suave" x="' + x(0) + '" y="' + (alto - 6) + '" text-anchor="middle">0</text>';
    s += "</svg>";
    return s;
  }

  function animacionPlacebo(a) {
    var ef = a.efecto, pl = a.placebo_adelanto.efecto;
    var frac = M.fraccionPlacebo(a);
    var W = 600, x0 = 12, ancho = W - 2 * x0 - 70;
    var esc = ancho / ef;
    var wPl = pl * esc, wEf = ef * esc;
    return '' +
      '<div class="tarjeta anim-tarjeta leccion">' +
      '<h3>El placebo de adelanto, paso a paso</h3>' +
      '<svg class="figura anim" id="anim" viewBox="0 0 ' + W + ' 210" role="img" aria-label="Animación del placebo de adelanto">' +
      '<defs><pattern id="rayado" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">' +
      '<rect width="8" height="8" fill="var(--causa)" opacity=".35"/><rect width="3" height="8" fill="var(--causa)"/></pattern></defs>' +
      '<text class="titulo-barra" x="' + x0 + '" y="22">Tres meses después de traer la nómina</text>' +
      '<rect class="barra b1" x="' + x0 + '" y="32" width="' + wEf + '" height="34" rx="4"/>' +
      '<text class="valor capa-v1" x="' + (x0 + wEf + 8) + '" y="55">' + M.pp(ef) + '</text>' +
      '<g class="capa"><rect class="sel" x="' + x0 + '" y="32" width="' + wPl + '" height="34" rx="4"/>' +
      '<rect class="resto" x="' + (x0 + wPl) + '" y="32" width="' + (wEf - wPl) + '" height="34"/>' +
      '<text x="' + (x0 + 8) + '" y="54" style="font-weight:700;fill:#1d2026">ya estaba antes: selección</text></g>' +
      '<text class="titulo-barra" x="' + x0 + '" y="112">Los que la traerán en 4 meses, antes de tenerla (placebo)</text>' +
      '<rect class="barra b2" x="' + x0 + '" y="122" width="' + wPl + '" height="34" rx="4"/>' +
      '<text class="valor" x="' + (x0 + wPl + 8) + '" y="145">' + M.pp(pl) + '</text>' +
      '<text class="suave" x="' + x0 + '" y="190">Diferencia en la tasa de clientes activos frente a clientes comparables (efecto en los tratados).</text>' +
      '</svg>' +
      '<p class="anim-pie" id="anim-pie" aria-live="polite"></p>' +
      '<button class="boton" id="anim-repetir">Repetir</button>' +
      '<p class="sub" style="margin-top:12px">Lo que queda (' + M.pp(ef - pl) + ') tampoco está probado: el placebo solo mira cuatro meses ' +
      'atrás, y el abono de la nómina puede contar como "actividad" por definición.</p>' +
      "</div>";
  }

  function correrAnimacion(a) {
    var svg = document.getElementById("anim");
    var pie = document.getElementById("anim-pie");
    if (!svg) return;
    var frac = Math.round(M.fraccionPlacebo(a) * 100);
    var textos = [
      "Quienes empiezan a recibir la nómina están " + M.pp(a.efecto) + " más activos tres meses después que clientes parecidos. Parece un efecto.",
      "Pero quienes la traerán dentro de cuatro meses ya están " + M.pp(a.placebo_adelanto.efecto) + " más activos antes de tenerla.",
      "Los " + frac + " % del supuesto efecto estaban ahí sin nómina: los clientes que se activan son los que la traen."
    ];
    var reducido = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    svg.setAttribute("class", "figura anim");
    pie.textContent = "";
    if (reducido) {
      svg.setAttribute("class", "figura anim paso1 paso2 paso3");
      pie.textContent = textos[2];
      return;
    }
    var pasos = [
      [400, "paso1", 0], [2600, "paso1 paso2", 1], [4800, "paso1 paso2 paso3", 2]
    ];
    pasos.forEach(function (p) {
      setTimeout(function () {
        svg.setAttribute("class", "figura anim " + p[1]);
        pie.textContent = textos[p[2]];
      }, p[0]);
    });
  }

  function predCausa(h5, id) {
    var s = h5.santander[id];
    if (!s || !s.predice_contra_causa || !s.predice_contra_causa.cate_medio_por_quintil_de_propension) return "";
    var q = s.predice_contra_causa.cate_medio_por_quintil_de_propension;
    var claves = Object.keys(q).sort();
    var vals = claves.map(function (k) { return q[k]; });
    var mn = Math.min.apply(null, vals.concat([0]));
    var W = 560, H = 180, izq = 40, abajo = 30;
    var ancho = (W - izq) / claves.length;
    var s2 = '<svg class="figura" viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="Efecto por quintil de propensión">';
    claves.forEach(function (k, i) {
      var h = (q[k] / mn) * (H - abajo - 20);
      s2 += '<rect x="' + (izq + i * ancho + 8) + '" y="12" width="' + (ancho - 16) + '" height="' + Math.max(h, 1) + '" fill="var(--causa)" rx="3"/>';
      s2 += '<text x="' + (izq + i * ancho + ancho / 2) + '" y="' + (Math.max(h, 1) + 28) + '" text-anchor="middle">' + M.pp(q[k]) + "</text>";
      s2 += '<text class="suave" x="' + (izq + i * ancho + ancho / 2) + '" y="' + (H - 6) + '" text-anchor="middle">Q' + k + "</text>";
    });
    s2 += "</svg>";
    return '<div class="tarjeta leccion"><h3>Lo que predice contra lo que causa, cliente a cliente</h3>' +
      '<p class="sub">Efecto estimado de adquirir el producto sobre la inactividad (más negativo = protege más), por quintil de la ' +
      "propensión a adquirirlo según el modelo predictivo (Q1 = los menos propensos, Q5 = los más).</p>" + s2 +
      "<p>Los clientes con <strong>más</strong> probabilidad de adquirirlo son aquellos en quienes adquirirlo <strong>menos</strong> " +
      "cambia (correlación de Spearman " + M.conSigno(s.predice_contra_causa.correlacion_spearman, 2) + "). Una campaña dirigida con el " +
      "modelo predictivo apuntaría donde la acción menos importa. Cautela: este efecto no pasó el placebo de adelanto.</p></div>";
  }

  function pintarPregunta(datos, p) {
    var a = datos.h4.analisis[p.id];
    var u = unidad(p.id);
    var cont = document.getElementById("pregunta");
    var pred = p.predice && datos.h2.shap[p.predice]
      ? '<p class="sub">' + p.prediceSub + "</p>" + barrasShap(datos.h2.shap[p.predice]) +
        '<p class="sub" style="margin-top:10px">Precisión promedio en prueba: ' + M.coma(datos.h2.productos[p.predice].modelo.ap, 3) +
        " (referencia simple: " + M.coma(datos.h2.productos[p.predice].referencia.ap, 3) + ").</p>"
      : "";
    var pruebas = Object.keys(NOMBRES_PRUEBAS).filter(function (k) { return k in a.pruebas; }).map(function (k) {
      var ok = a.pruebas[k];
      var cl = k === "sensibilidad_robusto" ? (ok ? "ok" : "info") : (ok ? "ok" : "no");
      return '<li><span class="marca ' + cl + '">' + (ok ? "✓" : (cl === "info" ? "!" : "✗")) + "</span><span>" + NOMBRES_PRUEBAS[k] + "</span></li>";
    }).join("");
    if (!("placebo_adelanto" in a.pruebas)) {
      pruebas += '<li><span class="marca info">–</span><span>Sin placebo de adelanto: el canal se fija al entrar.</span></li>';
    }
    cont.innerHTML =
      '<h2 class="pregunta-titulo">' + p.titulo + "</h2>" +
      '<div class="columnas">' +
      '<div class="tarjeta predice"><h3>Lo que predice</h3>' + pred + "<p>" + p.lecturaPredice + "</p></div>" +
      '<div class="tarjeta causa"><h3>Lo que causa</h3>' +
      '<p class="sub">Efecto en los clientes que lo hicieron, frente a clientes comparables que no (' + u.nombre + ").</p>" +
      '<div class="grande">' + u.f(a.efecto) + "</div>" +
      '<div class="ic">IC 95 %: ' + u.f(a.ic95[0]) + " a " + u.f(a.ic95[1]) + " · " + M.miles(a.n_tratados) + " tratados</div>" +
      '<span class="veredicto ' + claseVeredicto(a.veredicto) + '">' + a.veredicto + "</span>" +
      '<ul class="pruebas">' + pruebas + "</ul></div>" +
      "</div>" +
      (p.animacion ? animacionPlacebo(a) : "") +
      '<div class="tarjeta leccion"><h3>Todos los métodos' + (a.placebo_adelanto ? " y el placebo" : "") + "</h3>" +
      '<p class="sub">Punto: estimación; línea: IC 95 %. El placebo debería estar en cero.</p>' + bosque(a, u) + "</div>" +
      predCausa(datos.h5, p.id);
    if (p.animacion) {
      correrAnimacion(a);
      document.getElementById("anim-repetir").onclick = function () { correrAnimacion(a); };
    }
  }

  function iniciarPreguntas(datos) {
    var chips = document.getElementById("preguntas");
    PREGUNTAS.forEach(function (p, i) {
      var b = el('<button aria-pressed="' + (i === 0) + '">' + p.chip + "</button>");
      b.onclick = function () {
        chips.querySelectorAll("button").forEach(function (x) { x.setAttribute("aria-pressed", "false"); });
        b.setAttribute("aria-pressed", "true");
        pintarPregunta(datos, p);
        history.replaceState(null, "", "#" + p.id);
      };
      chips.appendChild(b);
    });
    var inicial = PREGUNTAS.filter(function (p) { return "#" + p.id === location.hash; })[0] || PREGUNTAS[0];
    chips.children[PREGUNTAS.indexOf(inicial)].click();
  }

  /* ---------- pestaña 2: simulador ---------- */

  function iniciarSimulador(sim) {
    var cont = document.getElementById("simulador");
    var acciones = sim.acciones;
    var nombresEstr = { nadie: "Nadie", todos_hombre: "Todos: correo de hombre", todos_mujer: "Todos: correo de mujer", arbol: "Árbol de política (hito 5)", propia: "Mi estrategia" };
    var estado = { costo: sim.costo_hito5, estrategia: "arbol", propia: sim.estrategias.arbol.slice() };
    document.querySelectorAll("[data-n-experimento]").forEach(function (x) { x.textContent = M.miles(sim.clientes_experimento); });

    cont.innerHTML =
      '<div class="controles">' +
      '<div class="costo"><label for="costo"><strong>Costo de cada correo</strong>, en visitas:</label>' +
      '<input type="range" id="costo" min="0" max="0.15" step="0.005">' +
      '<output id="costo-v"></output></div>' +
      '<div class="estrategias" id="estrategias"></div>' +
      "</div>" +
      '<div class="celdas" id="celdas"></div>' +
      '<div class="resultado">' +
      '<div class="tarjeta"><h3>Valor neto de la estrategia</h3><p class="sub">Visitas menos costo de los correos, por cada 1.000 clientes de prueba.</p>' +
      '<div class="grande" id="valor"></div><div class="ic" id="valor-ic"></div><p id="valor-txt"></p></div>' +
      '<div class="tarjeta"><h3>Comparación al costo elegido</h3><ul class="barras comparar" id="comparar"></ul></div>' +
      "</div>" +
      '<div class="aviso cuidado" id="aviso-mirar" hidden>Elegiste mirando estos mismos números de prueba: el valor queda inflado. ' +
      "El árbol del hito 5 se eligió <strong>sin</strong> ver la prueba; esa es la comparación honesta.</div>" +
      '<p class="sub" style="margin-top:12px">Celdas = qué ropa compraba el cliente × historia de compra, con el corte del árbol de política (' +
      M.miles(sim.corte_historia_usd) + " USD). Efectos medidos en la mitad de prueba (" + M.miles(sim.clientes_prueba) + " clientes). " +
      "El valor se estima por celdas; en el hito 5, con ponderación por la probabilidad de cada brazo, difiere en décimas.</p>";

    var r = document.getElementById("costo");
    r.value = estado.costo;
    r.oninput = function () { estado.costo = Number(r.value); pintar(); };

    var est = document.getElementById("estrategias");
    Object.keys(nombresEstr).forEach(function (k) {
      var b = el('<button class="boton" data-e="' + k + '">' + nombresEstr[k] + "</button>");
      b.onclick = function () { estado.estrategia = k; estado.miro = false; pintar(); };
      est.appendChild(b);
    });
    var mejor = el('<button class="boton">Lo mejor por celda, mirando la prueba</button>');
    mejor.onclick = function () {
      estado.propia = M.mejorPorCelda(sim.celdas, estado.costo);
      estado.estrategia = "propia"; estado.miro = true; pintar();
    };
    est.appendChild(mejor);

    function asignacion(k) { return k === "propia" ? estado.propia : sim.estrategias[k]; }

    function pintar() {
      document.getElementById("costo-v").textContent = M.coma(estado.costo, 3) + " visitas";
      est.querySelectorAll("[data-e]").forEach(function (b) {
        b.style.background = b.dataset.e === estado.estrategia ? "var(--texto)" : "";
        b.style.color = b.dataset.e === estado.estrategia ? "var(--papel)" : "";
      });
      var asig = asignacion(estado.estrategia);
      var celdas = document.getElementById("celdas");
      celdas.innerHTML = '<div class="celda encabezado"><span>Cliente</span><span>Efecto correo hombre</span><span>Efecto correo mujer</span><span>Acción</span></div>';
      sim.celdas.forEach(function (c, i) {
        var eh = M.efectoCelda(c, 1), em = M.efectoCelda(c, 2);
        var opciones = acciones.map(function (a, j) {
          return '<option value="' + j + '"' + (asig[i] === j ? " selected" : "") + ">" + a + "</option>";
        }).join("");
        var fila = el('<div class="celda">' +
          '<span class="quien"><strong>Compraba ' + c.comprador + "</strong><br><span class=\"n\">" + c.historia + " · " + M.miles(c.clientes_prueba) + " clientes</span></span>" +
          '<span data-titulo="Correo de hombre">' + M.pp(eh.efecto) + ' <span class="n">± ' + M.coma(1.96 * eh.ee * 100, 1) + "</span></span>" +
          '<span data-titulo="Correo de mujer">' + M.pp(em.efecto) + ' <span class="n">± ' + M.coma(1.96 * em.ee * 100, 1) + "</span></span>" +
          '<span class="accion"><select aria-label="Acción para esta celda">' + opciones + "</select></span></div>");
        fila.querySelector("select").onchange = function (ev) {
          estado.propia = asig.slice();
          estado.propia[i] = Number(ev.target.value);
          estado.estrategia = "propia"; estado.miro = false; pintar();
        };
        celdas.appendChild(fila);
      });
      var v = M.valorPolitica(sim.celdas, asig, estado.costo);
      document.getElementById("valor").textContent = M.coma(v.valor * 1000, 1);
      document.getElementById("valor-ic").textContent = "IC 95 %: " + M.coma((v.valor - 1.96 * v.ee) * 1000, 1) + " a " + M.coma((v.valor + 1.96 * v.ee) * 1000, 1);
      var nadie = M.valorPolitica(sim.celdas, sim.estrategias.nadie, estado.costo).valor;
      document.getElementById("valor-txt").textContent = "Correo a " + Math.round(v.fraccionConCorreo * 100) + " % de los clientes. " +
        (v.valor >= nadie ? "Frente a no mandar nada: " : "Pierde frente a no mandar nada: ") + M.conSigno((v.valor - nadie) * 1000, 1) + " visitas netas por cada 1.000.";
      document.getElementById("aviso-mirar").hidden = !estado.miro;
      var comp = document.getElementById("comparar");
      var claves = Object.keys(nombresEstr);
      var vals = claves.map(function (k) { return M.valorPolitica(sim.celdas, asignacion(k), estado.costo).valor; });
      var max = Math.max.apply(null, vals.map(function (x) { return Math.max(x, 0); })) || 1;
      comp.innerHTML = claves.map(function (k, i) {
        return '<li class="' + (k === estado.estrategia ? "actual" : "") + '"><span class="etiqueta">' + nombresEstr[k] + " · " +
          M.coma(vals[i] * 1000, 1) + '</span><span class="pista"><span class="relleno" style="display:block;width:' +
          (100 * Math.max(vals[i], 0) / max).toFixed(1) + '%"></span></span></li>';
      }).join("");
    }
    pintar();
  }

  /* ---------- pestañas ---------- */

  function iniciarPestanas() {
    var tabs = [["tab-pc", "panel-pc"], ["tab-sim", "panel-sim"]];
    tabs.forEach(function (t) {
      document.getElementById(t[0]).onclick = function () {
        tabs.forEach(function (u) {
          document.getElementById(u[0]).setAttribute("aria-selected", String(u === t));
          document.getElementById(u[1]).hidden = u !== t;
        });
      };
    });
    if (location.hash === "#simulador") document.getElementById("tab-sim").click();
  }

  function json(ruta) {
    return fetch(R + ruta).then(function (r) {
      if (!r.ok) throw new Error(ruta + ": " + r.status);
      return r.json();
    });
  }

  iniciarPestanas();
  Promise.all([json("hito4/estimaciones.json"), json("hito2/metricas.json"), json("hito5/heterogeneidad.json"),
    json("demo/hillstrom_celdas.json")]).then(function (r) {
    var datos = { h4: r[0], h2: r[1], h5: r[2] };
    iniciarPreguntas(datos);
    iniciarSimulador(r[3]);
  }).catch(function (e) {
    document.getElementById("pregunta").textContent = "No se pudieron cargar los resultados: " + e.message;
    console.error(e);
  });
})();
