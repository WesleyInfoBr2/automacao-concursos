
# 🧠 Automação de Monitoramento de Concursos Públicos  
### Coleta, classificação via IA e registro no Notion — 100% automatizado com n8n + Python + Docker

Este projeto implementa um pipeline completo de **web scraping, processamento, classificação semântica e registro de oportunidades** (concursos, bolsas, consultorias etc.) utilizando:

- **n8n (Docker)**  
- **Python (scraping)**  
- **OpenAI (classificação)**  
- **Notion (armazenamento estruturado)**  
- Execução **agendada semanalmente (Cron)**

O fluxo integra múltiplas fontes oficiais como PCI, UN Careers, CAPES e IPEA, filtra somente resultados relevantes e evita duplicações no Notion.

---

## 📌 Visão Geral do Fluxo

Workflow do n8n exportado: **Concurso_2.json**

---

## 🚀 Como funciona o pipeline

A execução semanal (segunda, 9h) percorre oito etapas principais:

### 1. Agendamento (Cron semanal)
### 2. Execução de scripts Python (scraping)
### 3. Merge e consolidação
### 4. Code para normalização
### 5. Verificação Notion (duplicidade)
### 6. Classificação OpenAI
### 7. Filtro de relevância
### 8. Formatação e criação no Notion

---

## 🗂️ Estrutura sugerida

```
automacao/
├── scripts/
├── n8n/
│   ├── docker-compose.yml
│   ├── Dockerfile
│   ├── Concurso_2.json
└── README.md
```

---

## 🐳 Docker — Ambiente Persistente

### docker-compose.yml

```yaml
services:
  n8n:
    image: n8nio/n8n:latest
    container_name: n8n
    restart: always
    ports:
      - "5678:5678"
    environment:
      - N8N_HOST=localhost
      - N8N_PORT=5678
      - N8N_PROTOCOL=http
      - EXECUTIONS_PROCESS=main
    volumes:
      - C:/Users/wesle/.n8n:/home/node/.n8n
      - ./scripts:/home/node/scripts
```

---

## 🧠 Prompt OpenAI

```json
{
  "relevante": true|false,
  "tags": ["..."],
  "justificativa": "..."
}
```

---

## 👨‍💻 Autor

Wesley Almeida
