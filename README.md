# ANP Monitor

Monitoramento automático de bases de dados da ANP (Agência Nacional do Petróleo, Gás Natural e Biocombustíveis) via GitHub Actions + Python.

Quando novos arquivos são detectados em uma base monitorada, o sistema envia alertas via **Telegram** e **e-mail**.

> **Por que repositório público?**
> GitHub Actions é gratuito e ilimitado em repositórios públicos. Em repositórios privados, o limite é 2.000 minutos/mês no plano gratuito.

---

## Bases monitoradas

| Base | Script | Workflow | Frequência |
|------|--------|----------|------------|
| [Síntese Semanal de Preços](https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-da-concorrencia/precos/sintese-semanal-do-comportamento-dos-precos-dos-combustiveis) | `scripts/monitor_sintese_semanal.py` | `.github/workflows/monitor_sintese_semanal.yml` | Terça 09h e 12h BRT, Quarta 09h BRT |

---

## Estrutura do repositório

```
anp-monitor/
├── scripts/
│   └── monitor_sintese_semanal.py   # Um script por base
├── state/
│   └── sintese_semanal_anp.json     # Estado persistido por base
├── .github/
│   └── workflows/
│       └── monitor_sintese_semanal.yml
├── requirements.txt
└── README.md
```

### Formato do estado (`state/*.json`)

```json
{
  "hash": "<sha256 do conjunto de URLs>",
  "urls": ["https://...arquivo1.xlsx", "..."],
  "last_checked": "2026-04-15T12:00:00+00:00",
  "last_updated": "2026-04-15T12:00:00+00:00",
  "new_links": []
}
```

---

## Configuração de Secrets

Acesse **Settings → Secrets and variables → Actions** no repositório e adicione:

| Secret | Descrição | Obrigatório |
|--------|-----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Token do bot (obtido via BotFather) | Não* |
| `TELEGRAM_CHAT_ID` | ID do chat/grupo para receber alertas | Não* |
| `SMTP_USER` | Endereço de e-mail remetente | Não* |
| `SMTP_PASSWORD` | Senha de app do Gmail (ou senha SMTP) | Não* |
| `SMTP_SERVER` | Servidor SMTP (padrão: `smtp.gmail.com`) | Não |
| `SMTP_PORT` | Porta SMTP (padrão: `587`) | Não |
| `ALERT_EMAIL_TO` | E-mail destinatário dos alertas | Não* |

*Se não configurado, o canal correspondente é silenciado sem erro.

---

## Como configurar o Telegram

1. Abra o Telegram e pesquise por **@BotFather**
2. Envie `/newbot` e siga as instruções para criar um bot
3. Copie o **token** gerado (formato: `123456789:ABCdef...`) → secret `TELEGRAM_BOT_TOKEN`
4. Para obter o **chat_id**:
   - Adicione o bot a um grupo, ou inicie uma conversa com ele
   - Acesse `https://api.telegram.org/bot<TOKEN>/getUpdates`
   - O `chat.id` aparece na resposta JSON → secret `TELEGRAM_CHAT_ID`

---

## Como configurar Gmail App Password

1. Ative a **verificação em duas etapas** na sua conta Google
2. Acesse [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
3. Crie uma senha de app com nome "ANP Monitor"
4. Use a senha de 16 caracteres gerada como secret `SMTP_PASSWORD`
5. Use seu endereço Gmail como `SMTP_USER` e `ALERT_EMAIL_TO`

---

## Como adicionar uma nova base

1. Copie `scripts/monitor_sintese_semanal.py` → `scripts/monitor_NOME_BASE.py`
2. Altere as constantes `URL`, `STATE_FILE`, `BASE_NAME` no novo script
3. Copie `.github/workflows/monitor_sintese_semanal.yml` → `.github/workflows/monitor_NOME_BASE.yml`
4. Ajuste o `name`, os crons e o comando `run` para apontar ao novo script
5. Crie `state/NOME_BASE.json` com conteúdo `{}`
6. Faça commit e push — o workflow será registrado automaticamente no GitHub Actions

---

## Execução manual

Acesse **Actions → Monitor Síntese Semanal ANP → Run workflow** para disparar uma execução imediata.

---

## Roadmap

- [ ] Dashboard HTML no GitHub Pages com histórico de detecções
- [ ] Alertas via WhatsApp (CallMeBot)
- [ ] Monitoramento de ~20-30 bases da ANP e outros órgãos do setor
