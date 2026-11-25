import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { readFileSync, readdirSync } from "node:fs";
import { test } from "node:test";

const PASTA = new URL("../src/typelead/web/js/", import.meta.url);

// Alguns arquivos só rodam no navegador, e nenhum outro teste os carrega. Pela entrada
// padrão porque o `node --check arquivo.js` deixa passar erros em módulos.
for (const nome of readdirSync(PASTA)) {
  test(`${nome} não tem erro de sintaxe`, () => {
    const { status, stderr } = spawnSync(process.execPath, ["--input-type=module", "--check", "-"], {
      input: readFileSync(new URL(nome, PASTA)),
    });
    assert.equal(status, 0, String(stderr));
  });
}

test("a verificação acusa um erro de verdade", () => {
  const { status } = spawnSync(process.execPath, ["--input-type=module", "--check", "-"], {
    input: 'import "x"; const a = "quebrada\n";',
  });
  assert.notEqual(status, 0);
});
