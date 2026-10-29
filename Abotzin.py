import os
import threading
from datetime import datetime
from zoneinfo import ZoneInfo
import discord
from discord.ext import commands
from dotenv import load_dotenv
from supabase import create_client
from flask import Flask

load_dotenv()

DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
EVENTO = os.getenv("EVENTO_ID", "evento-principal")
CANAL_ID = os.getenv("CANAL_REGISTRO_ID")  # opcional
DATA_EVENTO = os.getenv("DATA_EVENTO", "2026-11-08")  # formato AAAA-MM-DD
FUSO = ZoneInfo("America/Sao_Paulo")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

conversas = {}


def evento_e_hoje() -> bool:
    hoje = datetime.now(FUSO).date().isoformat()
    return hoje == DATA_EVENTO


@bot.event
async def on_ready():
    print(f"Bot online como {bot.user}")


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    if CANAL_ID and str(message.channel.id) != CANAL_ID:
        return

    user_id = message.author.id
    texto = (
        message.content.replace(f"<@{bot.user.id}>", "")
        .replace(f"<@!{bot.user.id}>", "")
        .strip()
    )
    foi_marcado = bot.user in message.mentions
    conversa = conversas.get(user_id)

    # Sem conversa em andamento: só responde se o bot for marcado
    if conversa is None:
        if not foi_marcado:
            return

        # No dia do evento, não registra: avisa e encerra
        if evento_e_hoje():
            await message.reply(
                "ixi não consigo pegar sua inscrição mais o evento é hoje 😕\n"
                "Mas você pode entrar e assistir ao evento, não precisa de ticket! "
                "Se quiser, pode vir em outro evento, ok?"
            )
            return

        conversas[user_id] = {"etapa": "nick"}
        await message.reply("Qual é o seu **nick no Mine**?")
        return

    if conversa["etapa"] == "nick":
        if not texto:
            await message.reply("Não entendi. Qual é o seu **nick no Mine**?")
            return
        conversa["nick"] = texto
        conversa["etapa"] = "raca"
        await message.reply("Certo! E qual é a sua **raça**?")
        return

    if conversa["etapa"] == "raca":
        if not texto:
            await message.reply("Não entendi. Qual é a sua **raça**?")
            return
        conversa["raca"] = texto
        conversa["etapa"] = "confirmar"
        await message.reply(
            f"Só para confirmar, seu nick é **{conversa['nick']}** e sua raça é **{conversa['raca']}**.\n"
            "Se sim, responda **sim** para participar do evento."
        )
        return

    if conversa["etapa"] == "confirmar":
        if texto.lower() in ("sim", "s", "yes"):
            try:
                supabase.table("inscricoes").upsert(
                    {
                        "evento": EVENTO,
                        "discord_id": str(user_id),
                        "discord_tag": str(message.author),
                        "nick_mine": conversa["nick"],
                        "raca": conversa["raca"],
                    },
                    on_conflict="evento,discord_id",
                ).execute()
            except Exception as e:
                print(f"Erro Supabase: {e}")
                await message.reply("❌ Erro ao salvar sua inscrição. Tente novamente mais tarde.")
                return

            await message.reply(
                f"Perfeito! ✅\n\nVocê está inscrito no evento com:\n\n"
                f"- **Nick:** {conversa['nick']}\n- **Raça:** {conversa['raca']}"
            )
            conversas.pop(user_id, None)
        else:
            await message.reply("Tudo bem, então vamos recomeçar. Qual é o seu **nick no Mine**?")
            conversa["etapa"] = "nick"
        return


# Servidor web mínimo para o Render manter o serviço ativo
app = Flask(__name__)


@app.route("/")
def health():
    return "Bot online"


def run_web():
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))


if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    bot.run(DISCORD_TOKEN)
