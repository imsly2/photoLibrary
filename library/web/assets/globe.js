(function () {
  const view = document.getElementById("globe-view");
  const canvas = document.getElementById("globe-canvas");
  const pinsEl = document.getElementById("globe-pins");
  const emptyEl = document.getElementById("globe-empty");
  const errorEl = document.getElementById("globe-error");
  const playBtn = document.getElementById("globe-play");
  const tourMedia = document.getElementById("globe-tour-media");
  const tourImage = document.getElementById("globe-tour-image");
  const tourVideo = document.getElementById("globe-tour-video");
  if (!view || !canvas || !pinsEl) {
    return;
  }

  const DEG_PER_PIXEL = 0.25;
  const ZOOM_FACTOR = 1.1;
  const CLUSTER_PX = 32;
  const PITCH_MAX = (90 - 0.05) * Math.PI / 180;
  const MIN_DIST = 1.18;
  const MAX_DIST = 6.5;
  const FOV = 45 * Math.PI / 180;
  const DRAG_SLOP = 4;
  const ORBIT_DEG_PER_SEC = 6;
  const EASE_SEC = 1;
  const CLOSE_DIST = 1.45;

  let gl = null;
  let program = null;
  let buffers = null;
  let indexCount = 0;
  let texture = null;
  let textureReady = false;
  let active = false;
  let places = [];
  let yaw = 0;
  let pitch = 0;
  let distance = 2.85;
  let dragging = false;
  let dragStartX = 0;
  let dragStartY = 0;
  let lastX = 0;
  let lastY = 0;
  let moving = false;
  let frozenGroups = null;
  let clusters = [];
  let raf = 0;
  let wheelTimer = 0;
  let cssWidth = 1;
  let cssHeight = 1;
  let pinSig = "";
  let touring = false;
  let phase = "idle";
  let phaseStarted = 0;
  let tourLastTs = 0;
  let tourList = [];
  let placeIndex = 0;
  let itemIndex = 0;
  let currentPlaceId = "";
  let currentItemId = "";
  let itemById = {};
  let orbitSec = 8;
  let pictureSec = 3;
  let orbitDistance = 2.85;
  let easeFrom = { yaw: 0, pitch: 0, distance: 2.85 };
  let easeTo = { yaw: 0, pitch: 0, distance: 2.85 };
  let mediaArmed = false;
  let loadTimer = 0;
  let emptyFromTour = false;

  function failWebgl(message) {
    if (errorEl) {
      errorEl.hidden = false;
      errorEl.textContent = message;
    }
    if (emptyEl) {
      emptyEl.hidden = true;
    }
    canvas.dataset.ready = "0";
    canvas.dataset.webgl = "0";
  }

  function toDeg(rad) {
    return rad * 180 / Math.PI;
  }

  function clamp(value, lo, hi) {
    return value < lo ? lo : value > hi ? hi : value;
  }

  function wrapYaw(value) {
    const two = Math.PI * 2;
    value = (value + Math.PI) % two;
    if (value < 0) {
      value += two;
    }
    return value - Math.PI;
  }

  function localFromLatLon(latDeg, lonDeg) {
    const lat = latDeg * Math.PI / 180;
    const lon = lonDeg * Math.PI / 180;
    const cl = Math.cos(lat);
    return [cl * Math.sin(lon), Math.sin(lat), cl * Math.cos(lon)];
  }

  function rotatePoint(v, yawVal, pitchVal) {
    const cy = Math.cos(yawVal);
    const sy = Math.sin(yawVal);
    const x = v[0] * cy + v[2] * sy;
    const y = v[1];
    const z = -v[0] * sy + v[2] * cy;
    const cp = Math.cos(pitchVal);
    const sp = Math.sin(pitchVal);
    return [x, y * cp - z * sp, y * sp + z * cp];
  }

  function inverseRotate(v, yawVal, pitchVal) {
    const cp = Math.cos(pitchVal);
    const sp = Math.sin(pitchVal);
    const x = v[0];
    const y = v[1] * cp + v[2] * sp;
    const z = -v[1] * sp + v[2] * cp;
    const cy = Math.cos(yawVal);
    const sy = Math.sin(yawVal);
    return [x * cy - z * sy, y, x * sy + z * cy];
  }

  function projectWorld(world, dist, width, height) {
    const viewZ = world[2] - dist;
    const f = 1 / Math.tan(FOV / 2);
    const aspect = width / Math.max(height, 1);
    if (viewZ >= -1e-4) {
      return { x: width / 2, y: height / 2, visible: false, world: world };
    }
    const x = (((world[0] * (f / aspect)) / -viewZ) * 0.5 + 0.5) * width;
    const y = ((-((world[1] * f) / -viewZ)) * 0.5 + 0.5) * height;
    return { x: x, y: y, visible: world[2] > 0.04, world: world };
  }

  function projectLatLon(lat, lon, yawVal, pitchVal, dist, width, height) {
    const local = localFromLatLon(lat, lon);
    const world = rotatePoint(local, yawVal, pitchVal);
    const proj = projectWorld(world, dist, width, height);
    proj.local = local;
    return proj;
  }

  function canvasPoint(clientX, clientY) {
    const rect = canvas.getBoundingClientRect();
    return {
      x: clientX - rect.left,
      y: clientY - rect.top,
      width: rect.width,
      height: rect.height,
      left: rect.left,
      top: rect.top,
    };
  }

  function intersectSphere(origin, dir) {
    const b = 2 * (dir[0] * origin[0] + dir[1] * origin[1] + dir[2] * origin[2]);
    const c = origin[0] * origin[0] + origin[1] * origin[1] + origin[2] * origin[2] - 1;
    const disc = b * b - 4 * c;
    if (disc < 0) {
      return null;
    }
    const t = (-b - Math.sqrt(disc)) / 2;
    if (t < 0) {
      return null;
    }
    return [origin[0] + dir[0] * t, origin[1] + dir[1] * t, origin[2] + dir[2] * t];
  }

  function pickCanvas(x, y) {
    const width = cssWidth;
    const height = cssHeight;
    const ndcX = (x / width) * 2 - 1;
    const ndcY = 1 - (y / height) * 2;
    const f = 1 / Math.tan(FOV / 2);
    const aspect = width / Math.max(height, 1);
    let dx = (ndcX * aspect) / f;
    let dy = ndcY / f;
    let dz = -1;
    const len = Math.hypot(dx, dy, dz) || 1;
    dx /= len;
    dy /= len;
    dz /= len;
    const origin = [0, 0, distance];
    const dir = [dx, dy, dz];
    const world = intersectSphere(origin, dir);
    if (!world) {
      return { hit: false, x: x, y: y };
    }
    const local = inverseRotate(world, yaw, pitch);
    const lat = Math.asin(clamp(local[1], -1, 1)) * 180 / Math.PI;
    const lon = Math.atan2(local[0], local[2]) * 180 / Math.PI;
    const proj = projectWorld(world, distance, width, height);
    const rect = canvas.getBoundingClientRect();
    return {
      hit: true,
      x: proj.x,
      y: proj.y,
      clientX: rect.left + proj.x,
      clientY: rect.top + proj.y,
      lat: lat,
      lon: lon,
      local: local,
      world: world,
    };
  }

  function yawPitchFor(local, world) {
    const gx = local[0];
    const gy = local[1];
    const gz = local[2];
    const tx = world[0];
    const ty = world[1];
    const tz = world[2];
    const r2 = gx * gx + gz * gz;
    const candidates = [];
    if (r2 < 1e-10) {
      candidates.push(yaw);
    } else {
      const r = Math.sqrt(r2);
      if (Math.abs(tx) > r + 1e-6) {
        return null;
      }
      const phi = Math.atan2(gz, gx);
      const alpha = Math.acos(clamp(tx / r, -1, 1));
      candidates.push(wrapYaw(phi + alpha), wrapYaw(phi - alpha));
    }
    let best = null;
    let bestErr = Infinity;
    candidates.forEach(function (yawVal) {
      const cy = Math.cos(yawVal);
      const sy = Math.sin(yawVal);
      const pry = gy;
      const prz = -gx * sy + gz * cy;
      let pitchVal = Math.atan2(tz, ty) - Math.atan2(prz, pry);
      if (pitchVal > Math.PI) {
        pitchVal -= Math.PI * 2;
      }
      if (pitchVal < -Math.PI) {
        pitchVal += Math.PI * 2;
      }
      pitchVal = clamp(pitchVal, -PITCH_MAX, PITCH_MAX);
      const got = rotatePoint(local, yawVal, pitchVal);
      const err = Math.hypot(got[0] - tx, got[1] - ty, got[2] - tz);
      if (err < bestErr) {
        bestErr = err;
        best = { yaw: yawVal, pitch: pitchVal };
      }
    });
    return bestErr < 0.05 ? best : null;
  }

  function keepAnchor(local, targetX, targetY) {
    if (!local) {
      return;
    }
    const ray = (function () {
      const ndcX = (targetX / cssWidth) * 2 - 1;
      const ndcY = 1 - (targetY / cssHeight) * 2;
      const f = 1 / Math.tan(FOV / 2);
      const aspect = cssWidth / Math.max(cssHeight, 1);
      let dx = (ndcX * aspect) / f;
      let dy = ndcY / f;
      let dz = -1;
      const len = Math.hypot(dx, dy, dz) || 1;
      return { origin: [0, 0, distance], dir: [dx / len, dy / len, dz / len] };
    })();
    const targetWorld = intersectSphere(ray.origin, ray.dir);
    if (targetWorld) {
      const aligned = yawPitchFor(local, targetWorld);
      if (aligned) {
        yaw = aligned.yaw;
        pitch = aligned.pitch;
        return;
      }
    }
    let bestYaw = yaw;
    let bestPitch = pitch;
    let bestErr = Infinity;
    for (let i = 0; i < 16; i += 1) {
      const world = rotatePoint(local, yaw, pitch);
      const proj = projectWorld(world, distance, cssWidth, cssHeight);
      const errX = targetX - proj.x;
      const errY = targetY - proj.y;
      const err = Math.hypot(errX, errY);
      if (err < bestErr) {
        bestErr = err;
        bestYaw = yaw;
        bestPitch = pitch;
      }
      if (err < 0.1) {
        return;
      }
      const eps = 0.0004;
      const pY = projectWorld(rotatePoint(local, yaw + eps, pitch), distance, cssWidth, cssHeight);
      const pP = projectWorld(rotatePoint(local, yaw, pitch + eps), distance, cssWidth, cssHeight);
      const j00 = (pY.x - proj.x) / eps;
      const j01 = (pP.x - proj.x) / eps;
      const j10 = (pY.y - proj.y) / eps;
      const j11 = (pP.y - proj.y) / eps;
      const det = j00 * j11 - j01 * j10;
      if (Math.abs(det) < 1e-12) {
        break;
      }
      const stepYaw = clamp((j11 * errX - j01 * errY) / det, -0.08, 0.08);
      const stepPitch = clamp((-j10 * errX + j00 * errY) / det, -0.08, 0.08);
      yaw = wrapYaw(yaw + stepYaw);
      pitch = clamp(pitch + stepPitch, -PITCH_MAX, PITCH_MAX);
    }
    yaw = bestYaw;
    pitch = bestPitch;
  }

  function compile(type, src) {
    const shader = gl.createShader(type);
    gl.shaderSource(shader, src);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
      throw new Error(gl.getShaderInfoLog(shader) || "shader");
    }
    return shader;
  }

  function mul4(a, b) {
    const out = new Float32Array(16);
    for (let col = 0; col < 4; col += 1) {
      for (let row = 0; row < 4; row += 1) {
        let sum = 0;
        for (let k = 0; k < 4; k += 1) {
          sum += a[k * 4 + row] * b[col * 4 + k];
        }
        out[col * 4 + row] = sum;
      }
    }
    return out;
  }

  function perspective(aspect) {
    const f = 1 / Math.tan(FOV / 2);
    const near = 0.1;
    const far = 20;
    const out = new Float32Array(16);
    out[0] = f / aspect;
    out[5] = f;
    out[10] = (far + near) / (near - far);
    out[11] = -1;
    out[14] = (2 * far * near) / (near - far);
    return out;
  }

  function modelMatrix() {
    const cy = Math.cos(yaw);
    const sy = Math.sin(yaw);
    const cp = Math.cos(pitch);
    const sp = Math.sin(pitch);
    const rotY = new Float32Array([
      cy, 0, -sy, 0,
      0, 1, 0, 0,
      sy, 0, cy, 0,
      0, 0, 0, 1,
    ]);
    const rotX = new Float32Array([
      1, 0, 0, 0,
      0, cp, sp, 0,
      0, -sp, cp, 0,
      0, 0, 0, 1,
    ]);
    return mul4(rotX, rotY);
  }

  function viewMatrix() {
    return new Float32Array([
      1, 0, 0, 0,
      0, 1, 0, 0,
      0, 0, 1, 0,
      0, 0, -distance, 1,
    ]);
  }

  function makeSphere(seg, rings) {
    const positions = [];
    const uvs = [];
    const indices = [];
    for (let j = 0; j <= rings; j += 1) {
      const v = j / rings;
      const lat = (0.5 - v) * Math.PI;
      const cy = Math.cos(lat);
      const sy = Math.sin(lat);
      for (let i = 0; i <= seg; i += 1) {
        const u = i / seg;
        const lon = (u - 0.5) * Math.PI * 2;
        positions.push(cy * Math.sin(lon), sy, cy * Math.cos(lon));
        uvs.push(u, v);
      }
    }
    for (let j = 0; j < rings; j += 1) {
      for (let i = 0; i < seg; i += 1) {
        const a = j * (seg + 1) + i;
        const b = a + seg + 1;
        indices.push(a, b, a + 1, a + 1, b, b + 1);
      }
    }
    return {
      positions: new Float32Array(positions),
      uvs: new Float32Array(uvs),
      indices: new Uint16Array(indices),
    };
  }

  function syncTourDataset() {
    canvas.dataset.tour = touring ? "1" : "0";
    canvas.dataset.tourPhase = phase;
    if (currentPlaceId) {
      canvas.dataset.tourPlaceId = currentPlaceId;
    } else {
      delete canvas.dataset.tourPlaceId;
    }
    if (currentItemId) {
      canvas.dataset.tourItemId = currentItemId;
    } else {
      delete canvas.dataset.tourItemId;
    }
  }

  function syncCameraDataset() {
    canvas.dataset.yaw = String(toDeg(yaw));
    canvas.dataset.pitch = String(toDeg(pitch));
    canvas.dataset.distance = String(distance);
    canvas.dataset.ready = textureReady ? "1" : "0";
    canvas.dataset.webgl = gl ? "1" : "0";
    syncTourDataset();
  }

  function framePlaces() {
    if (!places.length) {
      yaw = 0;
      pitch = 0;
      return;
    }
    let lat = 0;
    let lonX = 0;
    let lonZ = 0;
    places.forEach(function (place) {
      lat += place.latitude;
      const lon = place.longitude * Math.PI / 180;
      lonX += Math.cos(lon);
      lonZ += Math.sin(lon);
    });
    lat /= places.length;
    const lon = Math.atan2(lonZ, lonX) * 180 / Math.PI;
    yaw = wrapYaw(-lon * Math.PI / 180);
    pitch = clamp(lat * Math.PI / 180, -PITCH_MAX, PITCH_MAX);
  }

  function projectedPins() {
    const list = places.slice().sort(function (a, b) {
      return a.id < b.id ? -1 : a.id > b.id ? 1 : 0;
    });
    const rect = canvas.getBoundingClientRect();
    return list.map(function (place) {
      const proj = projectLatLon(place.latitude, place.longitude, yaw, pitch, distance, cssWidth, cssHeight);
      return {
        place: place,
        x: proj.x,
        y: proj.y,
        clientX: rect.left + proj.x,
        clientY: rect.top + proj.y,
        visible: proj.visible,
      };
    });
  }

  function clusterFromMembers(members) {
    if (!members.length) {
      return null;
    }
    members = members.slice().sort(function (a, b) {
      return a.place.id < b.place.id ? -1 : a.place.id > b.place.id ? 1 : 0;
    });
    let sx = 0;
    let sy = 0;
    let count = 0;
    members.forEach(function (member) {
      sx += member.x;
      sy += member.y;
      count += member.place.itemCount;
    });
    const rect = canvas.getBoundingClientRect();
    const x = sx / members.length;
    const y = sy / members.length;
    return {
      placeIds: members.map(function (member) {
        return member.place.id;
      }),
      itemCounts: members.map(function (member) {
        return member.place.itemCount;
      }),
      itemCount: count,
      newestCandidates: members.map(function (member) {
        return member.place.newestItemId;
      }),
      members: members,
      x: x,
      y: y,
      clientX: rect.left + x,
      clientY: rect.top + y,
    };
  }

  function computeClusters(pins) {
    const visible = pins.filter(function (pin) {
      return pin.visible;
    }).sort(function (a, b) {
      return a.place.id < b.place.id ? -1 : a.place.id > b.place.id ? 1 : 0;
    });
    const parent = visible.map(function (_, i) {
      return i;
    });
    function find(i) {
      while (parent[i] !== i) {
        parent[i] = parent[parent[i]];
        i = parent[i];
      }
      return i;
    }
    function union(a, b) {
      a = find(a);
      b = find(b);
      if (a === b) {
        return;
      }
      if (a < b) {
        parent[b] = a;
      } else {
        parent[a] = b;
      }
    }
    for (let i = 0; i < visible.length; i += 1) {
      for (let j = i + 1; j < visible.length; j += 1) {
        if (Math.hypot(visible[i].x - visible[j].x, visible[i].y - visible[j].y) <= CLUSTER_PX) {
          union(i, j);
        }
      }
    }
    const buckets = {};
    for (let i = 0; i < visible.length; i += 1) {
      const root = find(i);
      if (!buckets[root]) {
        buckets[root] = [];
      }
      buckets[root].push(visible[i]);
    }
    const out = Object.keys(buckets).map(function (key) {
      return clusterFromMembers(buckets[key]);
    }).filter(Boolean);
    out.sort(function (a, b) {
      return a.placeIds[0] < b.placeIds[0] ? -1 : 1;
    });
    return out;
  }

  function groupsFromPins(pins, membership) {
    const byId = {};
    pins.forEach(function (pin) {
      byId[pin.place.id] = pin;
    });
    return membership.map(function (ids) {
      return clusterFromMembers(ids.map(function (id) {
        return byId[id];
      }).filter(Boolean));
    }).filter(Boolean);
  }

  function renderPins() {
    const sig = clusters.map(function (cluster) {
      return cluster.placeIds.join(",") + ":" + cluster.itemCount;
    }).join("|");
    if (sig !== pinSig) {
      pinSig = sig;
      pinsEl.innerHTML = "";
      clusters.forEach(function (cluster, index) {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "globe-cluster";
        btn.textContent = String(cluster.itemCount);
        btn.dataset.placeIds = cluster.placeIds.join(",");
        btn.dataset.count = String(cluster.itemCount);
        btn.dataset.index = String(index);
        btn.addEventListener("click", function (event) {
          event.preventDefault();
          event.stopPropagation();
          if (window.libraryApp && window.libraryApp.openCluster) {
            window.libraryApp.openCluster(cluster.placeIds.slice());
          }
        });
        pinsEl.appendChild(btn);
      });
    }
    const buttons = pinsEl.querySelectorAll(".globe-cluster");
    clusters.forEach(function (cluster, index) {
      const btn = buttons[index];
      if (!btn) {
        return;
      }
      btn.style.left = cluster.x + "px";
      btn.style.top = cluster.y + "px";
      btn.dataset.placeIds = cluster.placeIds.join(",");
      btn.dataset.count = String(cluster.itemCount);
      btn.textContent = String(cluster.itemCount);
    });
  }

  function refreshClusters() {
    const pins = projectedPins();
    if (frozenGroups) {
      clusters = groupsFromPins(pins, frozenGroups);
    } else {
      clusters = computeClusters(pins);
    }
    renderPins();
  }

  function endMovement() {
    moving = false;
    frozenGroups = null;
    refreshClusters();
  }

  function beginMovement() {
    if (!moving) {
      frozenGroups = clusters.map(function (cluster) {
        return cluster.placeIds.slice();
      });
      moving = true;
    }
  }

  function drawGlobe() {
    if (!gl || !program || !active) {
      return;
    }
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    cssWidth = Math.max(1, rect.width);
    cssHeight = Math.max(1, rect.height);
    const pw = Math.max(1, Math.round(cssWidth * dpr));
    const ph = Math.max(1, Math.round(cssHeight * dpr));
    if (canvas.width !== pw || canvas.height !== ph) {
      canvas.width = pw;
      canvas.height = ph;
    }
    gl.viewport(0, 0, pw, ph);
    gl.clearColor(0.02, 0.02, 0.03, 1);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    if (!textureReady) {
      syncCameraDataset();
      return;
    }
    const mvp = mul4(perspective(cssWidth / cssHeight), mul4(viewMatrix(), modelMatrix()));
    gl.useProgram(program);
    gl.bindBuffer(gl.ARRAY_BUFFER, buffers.position);
    const aPos = gl.getAttribLocation(program, "aPosition");
    gl.enableVertexAttribArray(aPos);
    gl.vertexAttribPointer(aPos, 3, gl.FLOAT, false, 0, 0);
    gl.bindBuffer(gl.ARRAY_BUFFER, buffers.uv);
    const aUv = gl.getAttribLocation(program, "aUv");
    gl.enableVertexAttribArray(aUv);
    gl.vertexAttribPointer(aUv, 2, gl.FLOAT, false, 0, 0);
    gl.uniformMatrix4fv(gl.getUniformLocation(program, "uMVP"), false, mvp);
    const model = modelMatrix();
    gl.uniformMatrix3fv(gl.getUniformLocation(program, "uNormal"), false, [
      model[0], model[1], model[2],
      model[4], model[5], model[6],
      model[8], model[9], model[10],
    ]);
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, texture);
    gl.uniform1i(gl.getUniformLocation(program, "uTexture"), 0);
    gl.uniform3f(gl.getUniformLocation(program, "uLight"), 0.42, 0.38, 0.84);
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, buffers.index);
    gl.drawElements(gl.TRIANGLES, indexCount, gl.UNSIGNED_SHORT, 0);
    refreshClusters();
    syncCameraDataset();
    if (emptyEl) {
      const webglFailed = errorEl && !errorEl.hidden;
      if (emptyFromTour && !webglFailed) {
        emptyEl.hidden = false;
      } else {
        emptyEl.hidden = webglFailed || places.length > 0 || !textureReady;
      }
    }
  }

  function loop(now) {
    raf = 0;
    tickTour(now || performance.now());
    drawGlobe();
    if (active) {
      raf = window.requestAnimationFrame(loop);
    }
  }

  function requestDraw() {
    if (!active || raf) {
      return;
    }
    raf = window.requestAnimationFrame(loop);
  }

  function applyDrag(dx, dy) {
    yaw = wrapYaw(yaw + (dx * DEG_PER_PIXEL) * Math.PI / 180);
    pitch = clamp(pitch + (dy * DEG_PER_PIXEL) * Math.PI / 180, -PITCH_MAX, PITCH_MAX);
  }

  function syncSize() {
    const rect = canvas.getBoundingClientRect();
    cssWidth = Math.max(1, rect.width);
    cssHeight = Math.max(1, rect.height);
    return rect;
  }

  function applyWheel(event) {
    event.preventDefault();
    syncSize();
    const pt = canvasPoint(event.clientX, event.clientY);
    const pick = pickCanvas(pt.x, pt.y);
    beginMovement();
    const factor = event.deltaY < 0 ? 1 / ZOOM_FACTOR : ZOOM_FACTOR;
    distance = clamp(distance * factor, MIN_DIST, MAX_DIST);
    if (pick.hit) {
      keepAnchor(pick.local, pt.x, pt.y);
    }
    window.clearTimeout(wheelTimer);
    wheelTimer = window.setTimeout(endMovement, 120);
  }

  function loadTexture() {
    const image = new Image();
    image.onload = function () {
      if (!gl) {
        return;
      }
      texture = gl.createTexture();
      gl.bindTexture(gl.TEXTURE_2D, texture);
      gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, 0);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGB, gl.RGB, gl.UNSIGNED_BYTE, image);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      textureReady = true;
      canvas.dataset.texture = "/assets/earth.png";
      requestDraw();
    };
    image.onerror = function () {
      failWebgl("Earth texture is not available.");
    };
    image.src = "/assets/earth.png";
  }

  function initGl() {
    try {
      gl = canvas.getContext("webgl") || canvas.getContext("experimental-webgl");
    } catch (err) {
      gl = null;
    }
    if (!gl) {
      failWebgl("WebGL is not available.");
      return false;
    }
    if (errorEl) {
      errorEl.hidden = true;
      errorEl.textContent = "";
    }
    const vs = compile(gl.VERTEX_SHADER, [
      "attribute vec3 aPosition;",
      "attribute vec2 aUv;",
      "uniform mat4 uMVP;",
      "uniform mat3 uNormal;",
      "varying vec2 vUv;",
      "varying vec3 vNormal;",
      "void main() {",
      "  vUv = aUv;",
      "  vNormal = uNormal * aPosition;",
      "  gl_Position = uMVP * vec4(aPosition, 1.0);",
      "}",
    ].join("\n"));
    const fs = compile(gl.FRAGMENT_SHADER, [
      "precision mediump float;",
      "uniform sampler2D uTexture;",
      "uniform vec3 uLight;",
      "varying vec2 vUv;",
      "varying vec3 vNormal;",
      "void main() {",
      "  vec3 n = normalize(vNormal);",
      "  float light = 0.38 + 0.62 * max(dot(n, normalize(uLight)), 0.0);",
      "  vec3 color = texture2D(uTexture, vUv).rgb;",
      "  gl_FragColor = vec4(color * light, 1.0);",
      "}",
    ].join("\n"));
    program = gl.createProgram();
    gl.attachShader(program, vs);
    gl.attachShader(program, fs);
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      failWebgl("WebGL is not available.");
      return false;
    }
    const mesh = makeSphere(64, 48);
    buffers = {
      position: gl.createBuffer(),
      uv: gl.createBuffer(),
      index: gl.createBuffer(),
    };
    gl.bindBuffer(gl.ARRAY_BUFFER, buffers.position);
    gl.bufferData(gl.ARRAY_BUFFER, mesh.positions, gl.STATIC_DRAW);
    gl.bindBuffer(gl.ARRAY_BUFFER, buffers.uv);
    gl.bufferData(gl.ARRAY_BUFFER, mesh.uvs, gl.STATIC_DRAW);
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, buffers.index);
    gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, mesh.indices, gl.STATIC_DRAW);
    indexCount = mesh.indices.length;
    gl.enable(gl.DEPTH_TEST);
    gl.enable(gl.CULL_FACE);
    canvas.dataset.webgl = "1";
    loadTexture();
    return true;
  }

  function loadPlaces() {
    return fetch("/api/places").then(function (res) {
      if (!res.ok) {
        return [];
      }
      return res.json();
    }).then(function (data) {
      places = Array.isArray(data) ? data.filter(function (place) {
        return place && place.latitude != null && place.longitude != null;
      }) : [];
      if (!moving) {
        frozenGroups = null;
      }
      if (places.length && !canvas.dataset.framed) {
        framePlaces();
        canvas.dataset.framed = "1";
      }
      refreshClusters();
      return places;
    }).catch(function () {
      places = [];
      return places;
    });
  }

  function fetchJson(url) {
    return fetch(url).then(function (res) {
      if (!res.ok) {
        throw new Error("http");
      }
      return res.json();
    });
  }

  function applyTourSettings(settings) {
    if (!settings || typeof settings !== "object") {
      return;
    }
    if (typeof settings.tourOrbitSec === "number" && settings.tourOrbitSec > 0) {
      orbitSec = settings.tourOrbitSec;
    }
    if (typeof settings.tourPictureSec === "number" && settings.tourPictureSec > 0) {
      pictureSec = settings.tourPictureSec;
    }
  }

  function indexItems(items) {
    itemById = {};
    if (!Array.isArray(items)) {
      return;
    }
    items.forEach(function (item) {
      if (item && item.id) {
        itemById[item.id] = item;
      }
    });
  }

  function placeById(id) {
    for (let i = 0; i < places.length; i += 1) {
      if (places[i].id === id) {
        return places[i];
      }
    }
    return null;
  }

  function itemRecord(id) {
    return itemById[id] || null;
  }

  function lookAtPlace(place, dist) {
    return {
      yaw: wrapYaw(-place.longitude * Math.PI / 180),
      pitch: clamp(place.latitude * Math.PI / 180, -PITCH_MAX, PITCH_MAX),
      distance: dist,
    };
  }

  function shortestYaw(from, to) {
    let delta = to - from;
    const two = Math.PI * 2;
    while (delta > Math.PI) {
      delta -= two;
    }
    while (delta < -Math.PI) {
      delta += two;
    }
    return delta;
  }

  function applyEase(t) {
    if (!touring) {
      return;
    }
    const e = t * t * (3 - 2 * t);
    yaw = wrapYaw(easeFrom.yaw + shortestYaw(easeFrom.yaw, easeTo.yaw) * e);
    pitch = clamp(easeFrom.pitch + (easeTo.pitch - easeFrom.pitch) * e, -PITCH_MAX, PITCH_MAX);
    distance = easeFrom.distance + (easeTo.distance - easeFrom.distance) * e;
  }

  function clearLoadTimer() {
    if (loadTimer) {
      window.clearTimeout(loadTimer);
      loadTimer = 0;
    }
  }

  function hideTourMedia() {
    clearLoadTimer();
    if (tourVideo) {
      tourVideo.onloadeddata = null;
      tourVideo.onerror = null;
      tourVideo.pause();
      tourVideo.removeAttribute("src");
      try {
        tourVideo.load();
      } catch (err) {}
      tourVideo.hidden = true;
    }
    if (tourImage) {
      tourImage.onload = null;
      tourImage.onerror = null;
      tourImage.removeAttribute("src");
      tourImage.hidden = true;
    }
    if (tourMedia) {
      tourMedia.hidden = true;
    }
  }

  function showTourEmpty() {
    emptyFromTour = true;
    if (emptyEl) {
      emptyEl.textContent = (window.LibraryI18n && window.LibraryI18n.t("noLocations")) || "No locations to show";
      emptyEl.hidden = false;
    }
  }

  function clientEligible(item) {
    if (!item) {
      return false;
    }
    const status = ((item.renditions || {}).status || {});
    if (item.kind === "video") {
      return status.proxy === "ready";
    }
    if (item.kind === "photo" || item.kind === "live") {
      return !!tourStillWhich(item);
    }
    return false;
  }

  // A photo without a preview by design shows its original.
  function tourStillWhich(item) {
    const status = ((item.renditions || {}).status || {});
    if (status.preview === "ready") {
      return "preview";
    }
    return status.preview === "not-applicable" && item.available !== false ? "original" : "";
  }

  function armMedia() {
    if (!touring || phase !== "media") {
      return;
    }
    clearLoadTimer();
    mediaArmed = true;
    phaseStarted = performance.now();
    syncTourDataset();
  }

  function skipCurrentMedia() {
    if (!touring || phase !== "media") {
      return;
    }
    hideTourMedia();
    currentItemId = "";
    itemIndex += 1;
    mediaArmed = false;
    presentNextItem();
  }

  function showTourItem(item) {
    currentItemId = item.id;
    mediaArmed = false;
    phaseStarted = performance.now();
    syncTourDataset();
    clearLoadTimer();
    loadTimer = window.setTimeout(function () {
      skipCurrentMedia();
    }, 8000);
    if (item.kind === "video" && tourVideo && tourMedia) {
      if (tourImage) {
        tourImage.hidden = true;
      }
      tourVideo.hidden = false;
      tourMedia.hidden = false;
      tourVideo.muted = true;
      tourVideo.defaultMuted = true;
      tourVideo.volume = 0;
      tourVideo.loop = false;
      tourVideo.playsInline = true;
      tourVideo.onloadeddata = function () {
        if (!touring || phase !== "media" || currentItemId !== item.id) {
          return;
        }
        const play = tourVideo.play();
        if (play && play.catch) {
          play.catch(function () {});
        }
        armMedia();
      };
      tourVideo.onerror = function () {
        skipCurrentMedia();
      };
      tourVideo.src = window.libraryApp.mediaUrl(item.id, "proxy");
      return;
    }
    if ((item.kind === "photo" || item.kind === "live") && tourImage && tourMedia) {
      if (tourVideo) {
        tourVideo.hidden = true;
      }
      tourImage.hidden = false;
      tourMedia.hidden = false;
      tourImage.onload = function () {
        if (!touring || phase !== "media" || currentItemId !== item.id) {
          return;
        }
        armMedia();
      };
      tourImage.onerror = function () {
        skipCurrentMedia();
      };
      tourImage.src = window.libraryApp.mediaUrl(item.id, tourStillWhich(item));
      return;
    }
    skipCurrentMedia();
  }

  function presentNextItem() {
    const row = tourList[placeIndex];
    const ids = (row && row.itemIds) || [];
    while (itemIndex < ids.length) {
      const item = itemRecord(ids[itemIndex]);
      if (clientEligible(item)) {
        showTourItem(item);
        return;
      }
      itemIndex += 1;
    }
    startEaseOut();
  }

  function startOrbit() {
    const row = tourList[placeIndex];
    if (!row) {
      refetchCycle();
      return;
    }
    const place = placeById(row.placeId);
    if (!place) {
      placeIndex += 1;
      if (placeIndex >= tourList.length) {
        refetchCycle();
      } else {
        startOrbit();
      }
      return;
    }
    currentPlaceId = row.placeId;
    currentItemId = "";
    itemIndex = 0;
    mediaArmed = false;
    hideTourMedia();
    phase = "orbit";
    phaseStarted = performance.now();
    syncTourDataset();
  }

  function startEaseIn() {
    const place = placeById(currentPlaceId);
    if (!place) {
      advancePlace();
      return;
    }
    phase = "ease-in";
    phaseStarted = performance.now();
    easeFrom = { yaw: yaw, pitch: pitch, distance: distance };
    easeTo = lookAtPlace(place, CLOSE_DIST);
    syncTourDataset();
  }

  function startMedia() {
    phase = "media";
    mediaArmed = false;
    itemIndex = 0;
    currentItemId = "";
    hideTourMedia();
    presentNextItem();
    syncTourDataset();
  }

  function startEaseOut() {
    hideTourMedia();
    currentItemId = "";
    mediaArmed = false;
    phase = "ease-out";
    phaseStarted = performance.now();
    const place = placeById(currentPlaceId);
    easeFrom = { yaw: yaw, pitch: pitch, distance: distance };
    easeTo = place ? lookAtPlace(place, orbitDistance) : {
      yaw: yaw,
      pitch: pitch,
      distance: orbitDistance,
    };
    syncTourDataset();
  }

  function advancePlace() {
    placeIndex += 1;
    if (placeIndex >= tourList.length) {
      refetchCycle();
      return;
    }
    startOrbit();
  }

  function advanceMedia() {
    hideTourMedia();
    currentItemId = "";
    itemIndex += 1;
    mediaArmed = false;
    presentNextItem();
  }

  function finishEase(target) {
    if (!touring) {
      return;
    }
    yaw = target.yaw;
    pitch = target.pitch;
    distance = target.distance;
  }

  function cancelTourFrame() {
    if (raf) {
      window.cancelAnimationFrame(raf);
      raf = 0;
    }
    tourLastTs = 0;
  }

  function tickTour(now) {
    if (!touring) {
      tourLastTs = 0;
      return;
    }
    const dt = tourLastTs ? Math.min(0.05, (now - tourLastTs) / 1000) : 0;
    tourLastTs = now;
    const elapsed = (now - phaseStarted) / 1000;
    if (phase === "orbit") {
      if (!touring) {
        return;
      }
      yaw = wrapYaw(yaw + (ORBIT_DEG_PER_SEC * Math.PI / 180) * dt);
      if (elapsed >= orbitSec) {
        startEaseIn();
      }
    } else if (phase === "ease-in") {
      if (!touring) {
        return;
      }
      applyEase(Math.min(1, elapsed / EASE_SEC));
      if (elapsed >= EASE_SEC) {
        finishEase(easeTo);
        startMedia();
      }
    } else if (phase === "media") {
      if (mediaArmed && elapsed >= pictureSec) {
        advanceMedia();
      }
    } else if (phase === "ease-out") {
      if (!touring) {
        return;
      }
      applyEase(Math.min(1, elapsed / EASE_SEC));
      if (elapsed >= EASE_SEC) {
        finishEase(easeTo);
        advancePlace();
      }
    }
  }

  function filterTourRows(list) {
    if (!Array.isArray(list)) {
      return [];
    }
    return list.filter(function (row) {
      return row && row.placeId && Array.isArray(row.itemIds) && row.itemIds.length;
    });
  }

  function refetchCycle() {
    Promise.all([
      fetchJson("/api/globe/tour"),
      fetchJson("/api/settings"),
      fetchJson("/api/items"),
    ]).then(function (pair) {
      if (!touring) {
        return;
      }
      applyTourSettings(pair[1]);
      indexItems(pair[2]);
      const next = filterTourRows(pair[0]);
      if (!next.length) {
        stopTour();
        showTourEmpty();
        return;
      }
      tourList = next;
      placeIndex = 0;
      startOrbit();
    }).catch(function () {
      if (touring) {
        stopTour();
      }
    });
  }

  function beginTour(list, settings, items) {
    const rows = filterTourRows(list);
    if (!rows.length) {
      showTourEmpty();
      return;
    }
    emptyFromTour = false;
    if (emptyEl && places.length > 0) {
      emptyEl.hidden = true;
    }
    applyTourSettings(settings);
    indexItems(items);
    tourList = rows;
    placeIndex = 0;
    orbitDistance = distance;
    touring = true;
    tourLastTs = 0;
    beginMovement();
    startOrbit();
  }

  function startTour() {
    if (touring || !active) {
      return;
    }
    Promise.all([
      fetchJson("/api/globe/tour"),
      fetchJson("/api/settings"),
      fetchJson("/api/items"),
    ]).then(function (pair) {
      if (!active || touring) {
        return;
      }
      const list = filterTourRows(pair[0]);
      if (!list.length) {
        showTourEmpty();
        return;
      }
      beginTour(pair[0], pair[1], pair[2]);
    }).catch(function () {});
  }

  function stopTour() {
    const was = touring;
    if (!was && phase === "idle") {
      syncTourDataset();
      return false;
    }
    touring = false;
    cancelTourFrame();
    phase = "idle";
    currentPlaceId = "";
    currentItemId = "";
    mediaArmed = false;
    hideTourMedia();
    endMovement();
    syncTourDataset();
    if (active) {
      requestDraw();
    }
    return was;
  }

  function setActive(on) {
    active = !!on;
    if (!active) {
      stopTour();
    }
    if (active) {
      if (!gl && !canvas.dataset.webglTried) {
        canvas.dataset.webglTried = "1";
        initGl();
      }
      loadPlaces();
      requestDraw();
    } else if (raf) {
      window.cancelAnimationFrame(raf);
      raf = 0;
    }
    syncCameraDataset();
  }

  if (playBtn) {
    playBtn.addEventListener("click", function (event) {
      event.preventDefault();
      event.stopPropagation();
      startTour();
    });
  }

  view.addEventListener("wheel", function (event) {
    if (!active || event.ctrlKey) {
      return;
    }
    if (touring) {
      stopTour();
    }
    applyWheel(event);
  }, { passive: false });

  view.addEventListener("mousedown", function (event) {
    if (!active || event.button !== 0) {
      return;
    }
    if (event.target && event.target.closest && event.target.closest(".globe-cluster, #globe-play")) {
      return;
    }
    if (touring) {
      stopTour();
    }
    dragging = true;
    dragStartX = event.clientX;
    dragStartY = event.clientY;
    lastX = event.clientX;
    lastY = event.clientY;
    beginMovement();
    event.preventDefault();
  });
  window.addEventListener("mousemove", function (event) {
    if (!dragging) {
      return;
    }
    const dx = event.clientX - lastX;
    const dy = event.clientY - lastY;
    if (dx === 0 && dy === 0) {
      return;
    }
    applyDrag(dx, dy);
    lastX = event.clientX;
    lastY = event.clientY;
  });
  window.addEventListener("mouseup", function () {
    if (!dragging) {
      return;
    }
    dragging = false;
    endMovement();
  });

  window.addEventListener("resize", function () {
    if (active) {
      requestDraw();
    }
  });

  window.libraryGlobe = {
    setActive: setActive,
    refresh: loadPlaces,
    stopTour: stopTour,
    isTouring: function () {
      return touring;
    },
    getTour: function () {
      return {
        touring: touring,
        phase: phase,
        placeId: currentPlaceId,
        itemId: currentItemId,
        placeIndex: placeIndex,
        itemIndex: itemIndex,
      };
    },
    getCamera: function () {
      return {
        yawDeg: toDeg(yaw),
        pitchDeg: toDeg(pitch),
        distance: distance,
      };
    },
    pick: function (x, y) {
      return pickCanvas(x, y);
    },
    project: function (lat, lon) {
      const proj = projectLatLon(lat, lon, yaw, pitch, distance, cssWidth, cssHeight);
      const rect = canvas.getBoundingClientRect();
      return {
        x: proj.x,
        y: proj.y,
        clientX: rect.left + proj.x,
        clientY: rect.top + proj.y,
        visible: proj.visible,
      };
    },
    getClusters: function () {
      return clusters.map(function (cluster) {
        const pairwise = [];
        for (let i = 0; i < cluster.members.length; i += 1) {
          for (let j = i + 1; j < cluster.members.length; j += 1) {
            pairwise.push(Math.hypot(
              cluster.members[i].x - cluster.members[j].x,
              cluster.members[i].y - cluster.members[j].y
            ));
          }
        }
        return {
          placeIds: cluster.placeIds.slice(),
          itemCounts: cluster.itemCounts.slice(),
          itemCount: cluster.itemCount,
          newestCandidates: cluster.newestCandidates.slice(),
          centroid: { x: cluster.x, y: cluster.y, clientX: cluster.clientX, clientY: cluster.clientY },
          positions: cluster.members.map(function (member) {
            return {
              id: member.place.id,
              itemCount: member.place.itemCount,
              newestItemId: member.place.newestItemId,
              x: member.x,
              y: member.y,
              clientX: member.clientX,
              clientY: member.clientY,
            };
          }),
          pairwise: pairwise,
        };
      });
    },
    getPlaces: function () {
      return places.slice();
    },
  };
})();
