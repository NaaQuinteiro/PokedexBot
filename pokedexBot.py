import requests
import os
from dotenv import load_dotenv
import time


load_dotenv(".env")

TOKEN = os.getenv("TELEGRAM_TOKEN")
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"


# Buscar as ultimas mensagens do bot
def get_updates(offset=None):
    update_url = f"{BASE_URL}/getUpdates"

    if offset: 
        update_url += f"?offset={offset}"

    response = requests.get(update_url).json()

    if response["ok"] and response["result"]:
        return response["result"]
    return []


# Enviar uma mensagem normal
def send_message(chat_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text}

    if reply_markup:
        payload["reply_markup"] = reply_markup

    requests.post(f"{BASE_URL}/sendMessage", json=payload)


# Pegar a lista de pokemon de PokéAPI
def get_pokemon_list(limit=10, offset=0): 
    get_url = f"https://pokeapi.co/api/v2/pokemon?limit={limit}&offset={offset}"
    res = requests.get(get_url).json()

    return [p["name"].capitalize() for p in res["results"]]


# Buscar dados detalhados de um Pokemon

def get_pokemon_details(name):

    res = requests.get(f"https://pokeapi.co/api/v2/pokemon/{name.lower()}")

    if res.status_code != 200:
        return None
    
    data = res.json()
    types = ", ".join([t["type"]["name"] for t in data["types"]])

    # Pega a melhor imagem disponível
    img = (
        data["sprites"]["other"]["official-artwork"]["front_default"]
        or data["sprites"]["other"]["dream_world"]["front_default"]
        or data["sprites"]["front_default"]
    )

    return {
        "name": data["name"].capitalize(),
        "types": types,
        "height": data["height"],
        "weight": data["weight"],
        "xp": data["base_experience"],
        "img": img
    }



# Enviar uma lista de Pokemon como botões 
def send_pokemon_options(chat_id, offset=0):
    pokemons = get_pokemon_list(limit=5, offset=offset)
    keyboard = [[{"text": name, "callback_data": name.lower()}] for name in pokemons]
    keyboard.append(
        [
            {"text": "⬅️ Anterior", "callback_data": f"page:{max(offset-5, 0)}"},
            {"text": "➡️ Próxima", "callback_data": f"page:{offset+5}"}
        ]
    )
    markup = {"inline_keyboard": keyboard}
    send_message(chat_id, "Escolha um Pokémon:", reply_markup=markup)


# Confirma para o Telegram que a callback foi recebida
def answer_callback_query(callback_id):
    requests.post(f"{BASE_URL}/answerCallbackQuery", json={"callback_query_id": callback_id})


# Enviar uma imagem
def send_photo(chat_id, photo_url, caption):
    try:
        # Faz download da imagem
        response = requests.get(photo_url)
        response.raise_for_status()

        # Envia como arquivo (upload)
        files = {"photo": ("pokemon.png", response.content)}
        data = {
            "chat_id": chat_id,
            "caption": caption,
            "parse_mode": "Markdown"
        }

        r = requests.post(f"{BASE_URL}/sendPhoto", data=data, files=files)
        r.raise_for_status()

    except requests.RequestException as e:
        print("Erro ao enviar imagem:", e)
        # Se falhar, tenta fallback enviando apenas a URL
        requests.post(f"{BASE_URL}/sendPhoto", json={
            "chat_id": chat_id,
            "photo": photo_url,
            "caption": caption,
            "parse_mode": "Markdown"
        })


# Perguntar se deseja continuar 
def ask_continue(chat_id):
   
    keyboard = [
        [
            {"text": "✅ Sim", "callback_data": "continue:yes"},
            {"text": "❌ Não", "callback_data": "continue:no"},
        ]
    ]
    markup = {"inline_keyboard": keyboard}
    send_message(chat_id, "Deseja consultar outro Pokémon?", reply_markup=markup)


# ==============================
# Loop principal
# ==============================

def main():
    print("🤖 Bot da Pokédex iniciado!")
    offset = None

    while True:
        updates = get_updates(offset)
        for update in updates:
            offset = update["update_id"] + 1

            # Mensagem normal
            if "message" in update:
                chat_id = update["message"]["chat"]["id"]
                text = update["message"].get("text", "").lower()

                if text in ["/start", "/pokedex"]:
                    send_pokemon_options(chat_id)
                else:
                    send_message(chat_id, "Use /pokedex para começar! 😄")

            # Clique em botão (callback_query)
            elif "callback_query" in update:
                callback = update["callback_query"]
                chat_id = callback["message"]["chat"]["id"]
                data = callback["data"]
                callback_id = callback["id"]
                answer_callback_query(callback_id)

                # ======= PAGINAÇÃO =======
                if data.startswith("page:"):
                    offset_val = int(data.split(":")[1])
                    send_pokemon_options(chat_id, offset_val)

                # ======= DETALHE DO POKEMON =======
                elif not data.startswith("continue:"):
                    # Envia mensagem temporária de carregamento
                    send_message(chat_id, f" Buscando dados de {data.capitalize()}... ⏳")

                    poke = get_pokemon_details(data)

                    # Deleta a mensagem de carregamento 
                    send_message(chat_id, "🔎 Ainda coletando informações... quase lá!")

                    # Exibe os dados reais
                    if poke:
                        caption = (
                            f"✨ *{poke['name']}*\n"
                            f"Tipo: {poke['types']}\n"
                            f"Altura: {poke['height']}\n"
                            f"Peso: {poke['weight']}\n"
                            f"XP Base: {poke['xp']}"
                        )
                        send_photo(chat_id, poke["img"], caption)
                        # Pergunta se deseja continuar
                        ask_continue(chat_id)
                    else:
                        send_message(chat_id, "Pokémon não encontrado 😢")

                # ======= CONTINUAR OU ENCERRAR =======
                elif data.startswith("continue:"):
                    choice = data.split(":")[1]
                    if choice == "yes":
                        send_pokemon_options(chat_id)
                    else:
                        send_message(chat_id, "Até a próxima, treinador! 👋")


if __name__ == "__main__":
    main()