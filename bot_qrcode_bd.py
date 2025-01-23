import logging
import qrcode
import psycopg2
import os
import uuid
from dotenv import load_dotenv
from PIL import Image
from io import BytesIO
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from telegram import Update, InputMediaPhoto

# Carregar variáveis de ambiente do arquivo .env
load_dotenv()

# Configurações básicas
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")


PORT = int(os.getenv("PORT", 8443)) 

# Credenciais do banco de dados remoto
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_PORT = int(os.getenv("DB_PORT"))
app_url = os.getenv("APP_URL")

# Função para inicializar o banco de dados
def iniciar_banco():
    conn = psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        port=DB_PORT
    )
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ingressos (
            id SERIAL PRIMARY KEY,
            nome TEXT NOT NULL,
            qr_code_id TEXT NOT NULL,
            entrou BOOLEAN DEFAULT FALSE
        )
    ''')
    conn.commit()
    cursor.close()
    conn.close()

# Função para gerar QR Code com logo
def gerar_qr_code_com_logo(texto: str, logo_path: str, tamanho_logo: int = 100) -> BytesIO:
    qr = qrcode.QRCode(
        version=4,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4
    )
    qr.add_data(texto)
    qr.make(fit=True)
    img_qr = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    logo = Image.open(logo_path)
    logo = logo.resize((tamanho_logo, tamanho_logo), Image.LANCZOS)
    pos = (
        (img_qr.size[0] - logo.size[0]) // 2,
        (img_qr.size[1] - logo.size[1]) // 2
    )
    img_qr.paste(logo, pos, mask=logo if logo.mode == 'RGBA' else None)
    bio = BytesIO()
    img_qr.save(bio, format='PNG')
    bio.seek(0)
    return bio

# Função para salvar dados no banco
def salvar_dados(nome: str, qr_code_id: str):
    conn = psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        port=DB_PORT
    )
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO ingressos (nome, qr_code_id) VALUES (%s, %s)",
        (nome, qr_code_id)
    )
    conn.commit()
    cursor.close()
    conn.close()

# Função para deletar todos os dados do banco
def delete_command(update: Update, context: CallbackContext):
    conn = psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        port=DB_PORT
    )
    cursor = conn.cursor()
    cursor.execute("DELETE FROM ingressos")
    conn.commit()
    cursor.close()
    conn.close()
    update.message.reply_text("Todos os registros foram deletados do banco de dados.")

# Comandos do bot
def start(update: Update, context: CallbackContext):
    update.message.reply_text("Envie o nome + número de convites.\nExemplo: João 3")

def help_command(update: Update, context: CallbackContext):
    mensagem_ajuda = (
        "📖 *Comandos Disponíveis:*\n\n"
        "/start - Inicia a interação com o bot.\n"
        "/help - Mostra esta mensagem de ajuda.\n"
        "/total - Mostra o total de ingressos gerados.\n"
        "/norole - Mostra quantas pessoas já entraram no evento.\n"
        "/delete - Apaga todos os registros do banco de dados.\n\n"
        "📌 *Como gerar ingressos:*\n"
        "Envie o nome + número de convites.\n"
        "Exemplo: *João 3* (gera 3 QR Codes para João)"
    )
    update.message.reply_text(mensagem_ajuda, parse_mode='Markdown')

def total_command(update: Update, context: CallbackContext):
    conn = psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        port=DB_PORT
    )
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM ingressos")
    num_pessoas = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    update.message.reply_text(f"Já foram gerados {num_pessoas} ingressos")

def in_role_command(update: Update, context: CallbackContext):
    conn = psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        port=DB_PORT
    )
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM ingressos WHERE entrou = TRUE")
    num_pessoas = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    update.message.reply_text(f"Temos {num_pessoas} no role atualmente")

def receber_mensagem(update: Update, context: CallbackContext):
    mensagem = update.message.text.strip()
    partes = mensagem.split()
    if len(partes) < 2 or not partes[-1].isdigit():
        update.message.reply_text("Formato inválido! Envie no formato: Nome Quantidade\nExemplo: João 3")
        return

    nome_base = " ".join(partes[:-1])
    quantidade = int(partes[-1])
    if quantidade < 1:
        update.message.reply_text("Por favor, escolha uma quantidade maior que 1.")
        return

    lista_qrcodes = []
    for i in range(1, quantidade + 1):
        nome_completo = f"{nome_base}_{i}"
        qr_code_id = str(uuid.uuid4())
        texto_qr = qr_code_id
        qr_code_bytes = gerar_qr_code_com_logo(texto_qr, "logo.png")
        salvar_dados(nome_completo, qr_code_id)
        lista_qrcodes.append(InputMediaPhoto(qr_code_bytes, caption=f"Convite: {nome_completo}"))

    update.message.reply_media_group(media=lista_qrcodes)

def main():
    iniciar_banco()
    updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    # Adicionar handlers
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(CommandHandler("total", total_command))
    dispatcher.add_handler(CommandHandler("norole", in_role_command))
    dispatcher.add_handler(CommandHandler("delete", delete_command))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, receber_mensagem))

    # Usar webhook no Railway
    updater.start_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TELEGRAM_TOKEN,
        webhook_url=f"{app_url}/{TELEGRAM_TOKEN}"  # Substitua <sua-app>
    )
    updater.idle()

if __name__ == '__main__':
    main()