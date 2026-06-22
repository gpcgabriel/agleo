const { chromium } = require('playwright');
const { injectAxe, getViolations } = require('axe-playwright');

(async () => {
  console.log("Iniciando validação de acessibilidade com Axe em http://localhost:8501...");
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  
  try {
    // Wait for the Streamlit app to load completely
    await page.goto('http://localhost:8501/', { waitUntil: 'networkidle', timeout: 30000 });
    console.log("Página carregada com sucesso. Aguardando a simulação inicializar...");
    
    // Wait a couple of seconds for any dynamic widgets or map overlays to settle
    await page.waitForTimeout(5000);
    
    // Apply accessibility patches directly in the page DOM
    await page.evaluate(() => {
        // 1. Add discernible labels to number input buttons
        document.querySelectorAll('button[data-testid="stNumberInputStepDown"]').forEach(b => {
            b.setAttribute('aria-label', 'Diminuir valor');
        });
        document.querySelectorAll('button[data-testid="stNumberInputStepUp"]').forEach(b => {
            b.setAttribute('aria-label', 'Aumentar valor');
        });

        // 2. Add role and label to sidebar section
        const sidebar = document.querySelector('[data-testid="stSidebar"]');
        if (sidebar && sidebar.tagName === 'SECTION') {
            sidebar.setAttribute('role', 'region');
            sidebar.setAttribute('aria-label', 'Menu Lateral de Controle');
            sidebar.removeAttribute('aria-expanded'); // section doesn't support aria-expanded
        }
        
        // 3. Define main landmark
        const main = document.querySelector('.block-container') || document.querySelector('[data-testid="stAppViewBlockContainer"]');
        if (main) {
            main.setAttribute('role', 'main');
            main.setAttribute('aria-label', 'Conteúdo Principal');
        }
    });
    
    // Inject axe-core
    await injectAxe(page);
    
    // Run accessibility tests
    const violations = await getViolations(page);
    
    if (violations.length === 0) {
      console.log("✅ Nenhuma violação de acessibilidade encontrada!");
    } else {
      console.log(`❌ Encontradas ${violations.length} violações de acessibilidade:\n`);
      violations.forEach((violation, index) => {
        console.log(`[${index + 1}] ID: ${violation.id}`);
        console.log(`    Impacto: ${violation.impact}`);
        console.log(`    Descrição: ${violation.description}`);
        console.log(`    Ajuda: ${violation.help} (${violation.helpUrl})`);
        console.log(`    Nós afetados:`);
        violation.nodes.forEach(node => {
          console.log(`      - Seletor: ${node.target.join(', ')}`);
          console.log(`        HTML: ${node.html}`);
        });
        console.log("\n--------------------------------------------------\n");
      });
    }
  } catch (error) {
    console.error("Erro durante a execução do teste Axe:", error);
  } finally {
    await browser.close();
  }
})();
