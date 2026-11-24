import assert from "node:assert/strict";
import { test } from "node:test";

import { Player } from "../src/typelead/web/js/player.js";

// Um player de mentira, com os estados e os avisos do player do YouTube.
let falso;
globalThis.location = { origin: "http://localhost:8765" };
globalThis.window = globalThis;
globalThis.YT = {
  PlayerState: { ENDED: 0, PLAYING: 1, PAUSED: 2 },
  Player: class {
    tempo = 0;
    tocou = 0;
    constructor(_, { events }) {
      falso = this;
      this.eventos = events;
      queueMicrotask(() => events.onReady({}));
    }
    setOption() {}
    unloadModule() {}
    setPlaybackRate() {}
    seekTo(tempo) {
      this.tempo = tempo;
    }
    playVideo() {
      this.tocou += 1;
    }
    pauseVideo() {}
    getCurrentTime() {
      // Cada consulta encontra o vídeo um pouco mais adiante.
      this.tempo += this.tocou > 0 ? 0.3 : 0;
      return this.tempo;
    }
    falhar(codigo) {
      this.eventos.onError({ data: codigo });
    }
  },
};
globalThis.document = { createElement: () => ({}), head: { append: () => window.onYouTubeIframeAPIReady() } };

test("o erro que chega depois de o player ficar pronto é avisado e lembrado", async () => {
  const avisos = [];
  const player = await Player.criar({}, "id", (erro) => avisos.push(erro.codigo));
  falso.falhar(150);
  assert.deepEqual(avisos, [150]);
  assert.equal(player.impedimento.codigo, 150);
  await assert.rejects(player.tocarFala(0, 1), { codigo: 150 });
  await assert.rejects(player.tocarParaGravar(0, 1), { codigo: 150 });
  assert.equal(falso.tocou, 0);
});

test("uma falha passageira não impede de tentar de novo", async () => {
  const player = await Player.criar({}, "id");
  falso.falhar(5);
  assert.equal(player.impedimento, undefined);
  assert.equal(await player.tocarFala(0, 1), "fim");
});

test("sem erro, toca", async () => {
  const player = await Player.criar({}, "id");
  assert.equal(await player.tocarFala(3, 4), "fim");
});
