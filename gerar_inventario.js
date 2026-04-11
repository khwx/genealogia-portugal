/**
 * Gera inventario.json com todos os livros de Celorico da Beira
 * do tombo.pt (que é o frontend do Digitarq/ADGRD)
 *
 * Uso: node gerar_inventario.js
 */
const https = require('https');
const fs = require('fs');
const path = require('path');

const BASE_URL = 'https://tombo.pt';
const MUNICIPIO_URL = `${BASE_URL}/m/clb`;
const OUTPUT_FILE = path.join(__dirname, 'inventario.json');

function fetchPage(url) {
    return new Promise((resolve, reject) => {
        const opts = {
            headers: {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml',
                'Accept-Language': 'pt-PT,pt;q=0.9',
            },
            timeout: 30000,
        };
        https.get(url, opts, (res) => {
            let data = '';
            res.on('data', chunk => data += chunk);
            res.on('end', () => resolve(data));
        }).on('error', reject).on('timeout', () => reject(new Error('Timeout')));
    });
}

function sleep(ms) {
    return new Promise(r => setTimeout(r, ms));
}

// Extrai links /f/clb... do HTML
function extractFreguesias(html) {
    const matches = [...html.matchAll(/href="(\/f\/clb[^"]+)"/g)];
    const seen = new Set();
    const result = [];
    for (const m of matches) {
        const href = m[1];
        if (seen.has(href)) continue;
        seen.add(href);
        // Tentar extrair o nome
        const idx = html.indexOf(`href="${href}"`);
        const snippet = html.slice(idx, idx + 200);
        const nameMatch = snippet.match(/>([^<]{3,60})</);
        const name = nameMatch ? nameMatch[1].trim() : href.split('/').pop();
        result.push({ href, name });
    }
    return result;
}

// Extrai livros de óbitos de uma página de freguesia
function extractBooks(html, fregName) {
    const books = [];

    // Procurar tabelas de óbitos
    // A estrutura: <caption><h3>Registos de óbitos</h3></caption>
    const tableRegex = /<table[\s\S]*?<\/table>/gi;
    const tables = html.match(tableRegex) || [];

    for (const table of tables) {
        const lowerTable = table.toLowerCase();
        if (!lowerTable.includes('bitos') && !lowerTable.includes('obito')) continue;

        // Extrair linhas da tabela
        const rowRegex = /<tr[\s\S]*?<\/tr>/gi;
        const rows = table.match(rowRegex) || [];

        for (const row of rows) {
            // Procurar link com href para digitarq ou fileViewer
            const linkMatch = row.match(/href="([^"]*(?:digitarq|fileViewer|PT-ADGRD)[^"]*)"/i);
            const titleMatch = row.match(/title="([^"]+)"/);
            const textMatch = row.match(/>([^<]{5,100})</);

            if (!linkMatch) continue;

            const href = linkMatch[1];
            const titulo = titleMatch ? titleMatch[1] : (textMatch ? textMatch[1].trim() : '');

            // Extrair datas (formato: 1654-1790 ou 1654/1790)
            const datesMatch = row.match(/(\d{4})\s*[-\/]\s*(\d{4})/);
            const singleYearMatch = !datesMatch && row.match(/\b(\d{4})\b/);

            let data_inicio = '', data_fim = '';
            if (datesMatch) {
                data_inicio = datesMatch[1];
                data_fim = datesMatch[2];
            } else if (singleYearMatch) {
                data_inicio = singleYearMatch[1];
            }

            // Extrair código do livro do href
            const codigoMatch = href.match(/PT-ADGRD[^&?\s"]*/i) ||
                                href.match(/([A-Z0-9-]{10,})/);
            const codigo = codigoMatch ? codigoMatch[0] : '';

            // Construir URL do viewer
            let url_viewer = '';
            if (href.includes('fileViewer')) {
                url_viewer = href.startsWith('http') ? href : `https://digitarq.arquivos.pt${href}`;
            } else if (href.includes('digitarq')) {
                url_viewer = href;
            }

            if (titulo || codigo) {
                books.push({
                    freguesia: fregName,
                    titulo: titulo || `Livro de Óbitos`,
                    codigo: codigo,
                    data_inicio,
                    data_fim,
                    url_viewer,
                    url_source: href.startsWith('http') ? href : `${BASE_URL}${href}`,
                });
            }
        }
    }

    return books;
}

async function main() {
    console.log('🌳 Genealogia Portugal — A gerar inventário...');
    console.log(`   Fonte: ${MUNICIPIO_URL}\n`);

    // 1. Obter lista de freguesias
    console.log('📋 A obter lista de freguesias...');
    let municipioHtml;
    try {
        municipioHtml = await fetchPage(MUNICIPIO_URL);
    } catch (e) {
        console.error('❌ Erro ao aceder ao tombo.pt:', e.message);
        process.exit(1);
    }

    const freguesias = extractFreguesias(municipioHtml);
    console.log(`   ✅ ${freguesias.length} freguesias encontradas\n`);

    if (!freguesias.length) {
        console.error('❌ Nenhuma freguesia encontrada. A estrutura do tombo.pt pode ter mudado.');
        process.exit(1);
    }

    // 2. Para cada freguesia, extrair livros
    const allBooks = [];
    for (let i = 0; i < freguesias.length; i++) {
        const { href, name } = freguesias[i];
        const url = `${BASE_URL}${href}`;
        process.stdout.write(`   [${i + 1}/${freguesias.length}] ${name}... `);

        try {
            const html = await fetchPage(url);
            const books = extractBooks(html, name);
            allBooks.push(...books);
            console.log(`${books.length} livros`);
        } catch (e) {
            console.log(`❌ Erro: ${e.message}`);
        }

        await sleep(500); // Rate limiting gentil
    }

    // 3. Adicionar IDs e normalizar, filtrando quem não tem URL de imagens
    let validBooks = allBooks.filter(b => b.url_viewer && b.url_viewer.trim() !== '');

    const normalized = validBooks.map((b, i) => ({
        id: i + 1,
        ...b,
        paginas_indice: '',
        status: 'pendente',
    }));

    // 4. Guardar
    fs.writeFileSync(OUTPUT_FILE, JSON.stringify(normalized, null, 2), 'utf-8');
    console.log(`\n✅ ${normalized.length} livros guardados em: ${OUTPUT_FILE}`);
    console.log(`\n📊 Por freguesia:`);

    const byFreg = {};
    for (const b of normalized) {
        byFreg[b.freguesia] = (byFreg[b.freguesia] || 0) + 1;
    }
    for (const [freg, count] of Object.entries(byFreg).sort((a, b) => b[1] - a[1])) {
        console.log(`   ${freg}: ${count}`);
    }

    console.log(`\n🚀 Próximo passo: git add inventario.json && git commit && git push`);
}

main().catch(console.error);
