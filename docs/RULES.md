# RULES.md - Diretrizes Operacionais Baseadas em Feedback do Usuário

Este documento registra regras comportamentais e técnicas derivadas de correções e feedbacks negativos fornecidos pelo operador ao longo do desenvolvimento do painel LEOSim.

---

## 1. Localização e Execução de Testes
*   **Regra**: Todos os scripts de teste (de unidade, integração ou validação funcional) devem ser salvos e executados sob o diretório principal de testes do projeto: [tests/](file:///mnt/shared/projects/agleo/tests/).
*   **Motivo**: O operador negou explicitamente permissões para a criação e execução de scripts de teste temporários no diretório de rascunhos (`scratch/`).

## 2. Orquestração do Agente: Perguntas Informacionais vs. Ações
*   **Regra**: O agente orquestrador nunca deve acionar ferramentas de proposta (como adicionar satélites, criar usuários, alocar aplicações ou avançar a simulação) quando o operador estiver fazendo perguntas meramente informativas (ex: "Quantas aplicações foram alocadas?", "Teve alocação no GS 28?").
*   **Motivo**: O agente propôs incorretamente modificações na rede durante conversas informativas, gerando frustração ao usuário. O comportamento correto é responder textualmente utilizando apenas o resumo do estado do contexto.

## 3. Evitar Duplicação Visual e "Widgets Fantasmas"
*   **Regra**: Evite a renderização condicional de múltiplos widgets do mesmo tipo (como `st.chat_input`) em blocos `if`/`else` separados para representar estados diferentes. Em vez disso, use uma única chamada do widget com parâmetros dinâmicos (como placeholder e estado `disabled` variáveis) sob uma chave única (`key`).
*   **Motivo**: Transições de estado condicionais confundiam o algoritmo de diff do Streamlit, fazendo com que a tela de entrada do chat ou elementos de controle fossem desenhados em duplicidade no DOM.

## 4. Garantia de Contraste e Validação de Acessibilidade (Axe)
*   **Regra**: Qualquer alteração ou personalização visual de temas (especialmente modo escuro) deve ser rigorosamente inspecionada para evitar fontes escuras sobre fundos escuros e inputs com cores inconsistentes. Além disso, a hierarquia de títulos (`<h1>` a `<h6>` em ordem semântica correta), landmarks (`role="main"`) e `aria-label` descritivos para botões interativos devem ser validados via ferramentas Axe-core para garantir conformidade de acessibilidade (WCAG).
*   **Motivo**: Elementos como botões e campos de entrada numéricos no modo escuro apresentaram contrastes ilegíveis, e saltos na ordem de títulos geraram violações semânticas críticas de acessibilidade.
