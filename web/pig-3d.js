/* Сетка Пуни в координатах модели: +Y вверх, +Z к пятачку. */
const createPigView = (() => {
  const TAU = 2 * Math.PI;
  const vertexSource = `
    attribute vec3 a_position, a_normal;
    attribute vec4 a_material;
    uniform vec2 u_turn, u_scale;
    varying mediump vec3 v_position, v_normal;
    varying mediump vec4 v_material;

    vec3 camera(vec3 p) {
      vec3 yaw = vec3(u_turn.x * p.x + u_turn.y * p.z, p.y,
                      -u_turn.y * p.x + u_turn.x * p.z);
      return vec3(yaw.x, .986 * yaw.y - .167 * yaw.z, .167 * yaw.y + .986 * yaw.z);
    }

    void main() {
      vec3 p = camera(a_position - vec3(0., 1.31, 0.));
      gl_Position = vec4(p.xy * u_scale, -.4 * p.z, 1. - .13 * p.z);
      v_position = a_position;
      v_normal = camera(a_normal);
      v_material = a_material;
    }`;
  const fragmentSource = `
    #ifdef GL_FRAGMENT_PRECISION_HIGH
    precision highp float;
    #else
    precision mediump float;
    #endif
    varying mediump vec3 v_position, v_normal;
    varying mediump vec4 v_material;

    void main() {
      vec3 n = normalize(v_normal);
      float key = max(0., dot(n, vec3(-.47, .72, .51)));
      float fill = max(0., dot(n, vec3(.69, .16, .70)));
      float edge = pow(1. - abs(n.z), 2.);
      float light = .67 + .27 * key + .13 * fill + .07 * edge;

      // Мелкие волокна привязаны к поверхности, поэтому поворачиваются вместе с ней.
      vec3 fiber = fract(floor(v_position * 245.) * vec3(.1031, .1137, .1379));
      fiber += dot(fiber, fiber.yzx + 7.31);
      float grain = fract((fiber.x + fiber.y) * fiber.z) - .5;
      float knit = sin(v_position.y * 170. + 1.6 * cos(v_position.x * 115.))
                   * step(1.5, v_material.a);
      vec3 color = v_material.rgb * (light + grain * min(v_material.a, 1.) * .105 + knit * .045);
      color += vec3(.09, .045, .046) * (1. - key);
      gl_FragColor = vec4(color, 1.);
    }`;

  function mesh() {
    return {vertices: [], indices: []};
  }

  function surface(part, rows, columns, color, fabric, sample) {
    const rgb = [16, 8, 0].map((shift) => ((color >> shift) & 255) / 255);
    const offset = part.vertices.length / 10;
    for (let row = 0; row <= rows; row++) {
      for (let col = 0; col <= columns; col++) {
        const [position, normal] = sample(row / rows, col / columns);
        part.vertices.push(...position, ...normal, ...rgb, fabric);
        if (row < rows && col < columns) {
          const a = offset + row * (columns + 1) + col;
          const b = a + columns + 1;
          part.indices.push(a, a + 1, b, b, a + 1, b + 1);
        }
      }
    }
  }

  function ellipsoid(part, center, radii, color, fabric = 1, tilt = 0) {
    const c = Math.cos(tilt);
    const s = Math.sin(tilt);
    const rotate = ([x, y, z]) => [c * x - s * y, s * x + c * y, z];
    const detail = Math.max(...radii) > .34 ? 1 : 0;
    surface(part, detail ? 20 : 12, detail ? 30 : 18, color, fabric, (v, u) => {
      const theta = Math.PI * v;
      const phi = TAU * u;
      const unit = [Math.sin(theta) * Math.cos(phi), Math.cos(theta), Math.sin(theta) * Math.sin(phi)];
      const position = rotate(unit.map((value, i) => value * radii[i]));
      const normal = rotate(unit.map((value, i) => value / radii[i]));
      return [position.map((value, i) => value + center[i]), normalize(normal)];
    });
  }

  function normalize(vector) {
    const length = Math.hypot(...vector);
    return vector.map((value) => value / length);
  }

  function cross([a, b, c], [x, y, z]) {
    return [b * z - c * y, c * x - a * z, a * y - b * x];
  }

  function tube(part, points, radius, color, fabric = 0, closed = false) {
    const last = points.length - 1;
    surface(part, last, 8, color, fabric, (v, u) => {
      const row = Math.round(v * last);
      const before = points[row === 0 && closed ? last - 1 : Math.max(0, row - 1)];
      const after = points[row === last && closed ? 1 : Math.min(last, row + 1)];
      const tangent = normalize(after.map((value, i) => value - before[i]));
      const axis = Math.abs(tangent[2]) > .8 ? [0, 1, 0] : [0, 0, 1];
      const right = normalize(cross(tangent, axis));
      const up = cross(right, tangent);
      const normal = right.map((value, i) => value * Math.cos(TAU * u) + up[i] * Math.sin(TAU * u));
      return [points[row].map((value, i) => value + radius * normal[i]), normal];
    });
  }

  function curve(segments, pointAt) {
    return Array.from({length: segments + 1}, (_, i) => pointAt(i / segments));
  }

  function model() {
    const body = mesh();
    const belly = mesh();
    const eyes = mesh();
    const sleepyEyes = mesh();
    const smile = mesh();
    const frown = mesh();
    const pink = 0xf5adc4;
    const hoof = 0xd986a3;
    const thread = 0x643b4b;

    ellipsoid(body, [0, .65, -.13], [.69, .64, .63], pink);
    ellipsoid(belly, [0, .59, .32], [.47, .42, .22], 0xffd4de);
    for (const side of [-1, 1]) {
      for (const z of [-.46, .38]) {
        ellipsoid(body, [side * .40, .23, z], [.22, .23, .22], pink);
        ellipsoid(body, [side * .40, .131, z + .022], [.218, .133, .225], hoof);
        tube(body, [[side * .40, .10, z + .246], [side * .40, .15, z + .249]], .012, 0xb97490);
      }
      const tilt = -side * .43;
      ellipsoid(body, [side * .53, 2.00, .015], [.23, .40, .17], 0xef9fba, 1, tilt);
      ellipsoid(body, [side * .57, 2.05, .145], [.145, .273, .069], 0xe485a8, 1, tilt);
    }
    const curl = curve(32, (t) => {
      const radius = .17 - .107 * t;
      return [.18 + radius * Math.sin(TAU * t * 1.35), .78 - radius * Math.cos(TAU * t * 1.35), -.90 - .30 * t];
    });
    tube(body, [[.08, .54, -.69], [.115, .59, -.80], ...curl], .058, 0xea97b3, 1);
    ellipsoid(body, curl[curl.length - 1], [.058, .058, .058], 0xea97b3);
    for (let i = 0; i < 7; i++) {
      const y = .80 + i * .055;
      const z = -.13 - .63 * Math.sqrt(1 - ((y - .65) / .64) ** 2);
      tube(body, [[-.017, y - .008, z - .005], [.017, y + .008, z - .006]], .008, 0xd78da8, 1);
    }

    ellipsoid(body, [0, 1.47, .12], [.77, .67, .66], 0xf9b8cc);
    ellipsoid(body, [0, 1.34, .708], [.331, .230, .239], 0xee96b3);
    for (const side of [-1, 1]) {
      const x = side * .32;
      ellipsoid(body, [side * .49, 1.38, .607], [.155, .108, .048], 0xf295b2, 1, side * .18);
      ellipsoid(body, [side * .115, 1.36, .928], [.047, .061, .021], 0xb26783, 1, side * .12);
      ellipsoid(eyes, [x, 1.63, .699], [.066, .085, .062], thread, 0);
      ellipsoid(eyes, [x - .017, 1.655, .752], [.021, .022, .014], 0xfff0f4, 0);
      tube(sleepyEyes, curve(10, (t) => [x - .067 + .134 * t, 1.63 - .027 * Math.sin(t * Math.PI),
        .730 - side * .058 * (t - .5)]), .013, thread);
    }
    for (const [mouth, direction] of [[smile, -1], [frown, 1]]) {
      tube(mouth, curve(12, (t) => [t * .183 - .0915, 1.071 + direction * .032 * Math.sin(t * Math.PI),
        .663 + direction * .019 * Math.sin(t * Math.PI)]), .014, thread);
    }

    const bow = mesh();
    for (const side of [-1, 1]) {
      ellipsoid(bow, [.60 + side * .121, 1.985 + side * .045, .277], [.132, .086, .064], 0xda507f, 1, side * .48 + .34);
      ellipsoid(bow, [.60 + side * .064, 1.89, .260], [.039, .106, .032], 0xd34978, 1, side * .42);
    }
    ellipsoid(bow, [.60, 1.985, .336], [.065, .064, .047], 0xf581aa);

    const glasses = mesh();
    for (const side of [-1, 1]) {
      const frame = curve(32, (t) => [side * .32 + .180 * Math.cos(TAU * t),
        1.60 + .153 * Math.sin(TAU * t), .808 - side * .042 * Math.cos(TAU * t)]);
      tube(glasses, frame, .024, 0x62447e, 0, true);
      tube(glasses, [[side * .497, 1.62, .774], [side * .571, 1.64, .729],
        [side * .683, 1.65, .572], [side * .704, 1.61, .399]], .021, 0x62447e);
    }
    tube(glasses, [[-.151, 1.62, .85], [-.08, 1.665, .865], [0, 1.673, .87],
      [.08, 1.665, .865], [.151, 1.62, .85]], .023, 0x62447e);

    const hat = mesh();
    ellipsoid(hat, [0, 2.19, -.04], [.752, .075, .643], 0x95bfae);
    ellipsoid(hat, [0, 2.31, -.04], [.488, .286, .436], 0xa9cfbd);
    ellipsoid(hat, [0, 2.236, -.04], [.480, .093, .428], 0xffe5bb);
    for (const [x, y] of [[0, 2.37], [.042, 2.33], [0, 2.29], [-.042, 2.33]]) {
      ellipsoid(hat, [x, y, .401], [.037, .036, .017], 0xfff2d2);
    }
    ellipsoid(hat, [0, 2.33, .418], [.029, .029, .017], 0xf1b65e);

    const sweater = mesh();
    ellipsoid(sweater, [0, .655, -.11], [.723, .657, .660], 0x997ec2, 2);
    ellipsoid(sweater, [0, .367, -.10], [.680, .205, .621], 0xab90d1, 2);
    const heart = curve(28, (t) => {
      const angle = TAU * t;
      const x = .139 * Math.sin(angle) ** 3;
      const y = .62 + .008 * (13 * Math.cos(angle) - 5 * Math.cos(2 * angle)
        - 2 * Math.cos(3 * angle) - Math.cos(4 * angle));
      return [x, y, -.11 + .660 * Math.sqrt(1 - (x / .723) ** 2 - ((y - .655) / .657) ** 2)];
    });
    tube(sweater, heart, .019, 0xf4c9df, 2, true);
    for (const side of [-1, 1]) {
      ellipsoid(sweater, [side * .533, .48, .22], [.205, .267, .244], 0xb399d8, 2, side * .36);
      ellipsoid(sweater, [side * .558, .325, .255], [.180, .084, .205], 0x9476bd, 2, side * .30);
    }

    const overalls = mesh();
    const denim = 0x668cbb;
    ellipsoid(overalls, [0, .421, -.13], [.69, .413, .639], denim, 2);
    ellipsoid(overalls, [0, .67, .411], [.404, .391, .189], denim, 2);
    ellipsoid(overalls, [0, .58, .588], [.176, .127, .041], 0x8aabd1, 2);
    for (const side of [-1, 1]) {
      tube(overalls, [[side * .32, .78, .535], [side * .36, .95, .467], [side * .41, 1.07, .31],
        [side * .44, 1.10, .08], [side * .45, 1.035, -.236], [side * .40, .88, -.53],
        [side * .35, .72, -.656]], .066, 0x7ca1cb, 2);
      ellipsoid(overalls, [side * .32, .797, .589], [.050, .048, .025], 0xffd580, 0);
    }
    return {body, belly, eyes, sleepyEyes, smile, frown, bow, glasses, hat, sweater, overalls};
  }

  function programFor(gl) {
    const program = gl.createProgram();
    for (const [type, source] of [[gl.VERTEX_SHADER, vertexSource], [gl.FRAGMENT_SHADER, fragmentSource]]) {
      const shader = gl.createShader(type);
      gl.shaderSource(shader, source);
      gl.compileShader(shader);
      if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
        throw new Error(gl.getShaderInfoLog(shader));
      }
      gl.attachShader(program, shader);
      gl.deleteShader(shader);
    }
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(program));
    return program;
  }

  function renderer(gl) {
    const program = programFor(gl);
    const attributes = ['a_position', 'a_normal', 'a_material'].map((name) => gl.getAttribLocation(program, name));
    const scale = gl.getUniformLocation(program, 'u_scale');
    const turn = gl.getUniformLocation(program, 'u_turn');
    const parts = new Map();
    gl.useProgram(program);
    gl.enable(gl.DEPTH_TEST);
    attributes.forEach((location) => gl.enableVertexAttribArray(location));
    for (const [id, {vertices, indices}] of Object.entries(model())) {
      const vertexBuffer = gl.createBuffer();
      const indexBuffer = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, vertexBuffer);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(vertices), gl.STATIC_DRAW);
      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, indexBuffer);
      gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, new Uint16Array(indices), gl.STATIC_DRAW);
      parts.set(id, {vertexBuffer, indexBuffer, count: indices.length});
    }
    return (width, height, yaw, visibleParts) => {
      gl.viewport(0, 0, width, height);
      gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
      gl.uniform2f(scale, .66 * height / width, .66);
      gl.uniform2f(turn, Math.cos(yaw), Math.sin(yaw));
      for (const id of visibleParts) {
        const {vertexBuffer, indexBuffer, count} = parts.get(id);
        gl.bindBuffer(gl.ARRAY_BUFFER, vertexBuffer);
        attributes.forEach((location, i) => gl.vertexAttribPointer(location, i === 2 ? 4 : 3, gl.FLOAT, false, 40, 12 * i));
        gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, indexBuffer);
        gl.drawElements(gl.TRIANGLES, count, gl.UNSIGNED_SHORT, 0);
      }
    };
  }

  return function createPigView(canvas, onAvailability) {
    const gl = canvas.getContext('webgl', {powerPreference: 'low-power'});
    if (!gl) return null;
    let draw;
    let yaw = -.28;
    let visibleParts = ['body', 'eyes', 'smile', 'bow', 'belly'];
    let frame = 0;

    function scheduleDraw() {
      if (!draw || frame) return;
      frame = requestAnimationFrame(() => {
        frame = 0;
        if (!draw || canvas.hidden) return;
        const density = Math.min(window.devicePixelRatio || 1, 2);
        const width = Math.round(canvas.clientWidth * density);
        const height = Math.round(canvas.clientHeight * density);
        if (!width || !height) return;
        if (canvas.width !== width) canvas.width = width;
        if (canvas.height !== height) canvas.height = height;
        draw(width, height, yaw, visibleParts);
      });
    }

    function setup() {
      try {
        draw = renderer(gl);
      } catch (error) {
        console.warn('Не удалось запустить 3D Пуню.', error);
      }
      onAvailability(Boolean(draw));
      scheduleDraw();
    }

    canvas.addEventListener('webglcontextlost', (event) => {
      event.preventDefault();
      draw = null;
      onAvailability(false);
    });
    canvas.addEventListener('webglcontextrestored', setup);
    window.addEventListener('resize', scheduleDraw);
    setup();

    return {
      turn(angle) {
        yaw = (yaw + angle) % TAU;
        scheduleDraw();
      },
      update(outfit, mood) {
        const eyes = ['sleeping', 'tired'].includes(mood) ? 'sleepyEyes' : 'eyes';
        const mouth = ['sad', 'sick', 'hungry'].includes(mood) ? 'frown' : 'smile';
        const nextParts = ['body', eyes, mouth, ...Object.values(outfit)];
        if (!outfit.body) nextParts.push('belly');
        if (visibleParts.join() === nextParts.join()) return;
        visibleParts = nextParts;
        scheduleDraw();
      },
    };
  };
})();
