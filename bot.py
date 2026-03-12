import discord
from discord.ext import commands


intents = discord.Intents.default()
intents.message_content = True  # allows bot to read text messages

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Logged in as {bot.user}")

@bot.event
async def on_close():
    conn.close()

@bot.command()
async def ping(ctx):
    await ctx.send("Pong!")

import datetime
import sqlite3

# this should connect to database
conn = sqlite3.connect("economy.db")
cursor = conn.cursor()

#create the table
cursor.execute("""
CREATE TABLE IF NOT EXISTS economy (
    user_id TEXT PRIMARY KEY,
    balance INTEGER,
    streak INTEGER,
    last_daily TEXT
)
""")

# add last_getajob
cursor.execute("PRAGMA table_info(economy)")
columns = [info[1] for info in cursor.fetchall()]

if "last_getajob" not in columns:
    cursor.execute("ALTER TABLE economy ADD COLUMN last_getajob TEXT")
    conn.commit()
    print("Added missing column: last_getajob")

conn.commit()

@bot.tree.command(name="ping", description="Test if slash commands work")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("Pong!")


def get_balance(user_id):
    user_id = str(user_id)
    cursor.execute("SELECT balance FROM economy WHERE user_id = ?", (str(user_id),))
    row = cursor.fetchone()
    if row is None:
        # make new row if user doesnt exist
        cursor.execute("INSERT INTO economy (user_id, balance, streak, last_daily) VALUES (?, ?, ?, ?)",
                       (str(user_id), 0, 0, None))
        conn.commit()
        return 0
    return row[0]

def add_money(user_id, amount):
    user_id = str(user_id)
    get_balance(user_id)
    cursor.execute("UPDATE economy SET balance = balance + ? WHERE user_id = ?", (amount, str(user_id)))
    conn.commit()

def set_last_getajob(user_id, timestamp):
    cursor.execute("UPDATE economy SET last_getajob = ? WHERE user_id = ?", (timestamp, str(user_id)))
    conn.commit()

def get_last_getajob(user_id):
    cursor.execute("SELECT last_getajob FROM economy WHERE user_id = ?", (str(user_id),))
    row = cursor.fetchone()
    return row[0] if row else None

@bot.tree.command(name="give", description="(Dev only)")
async def give(interaction: discord.Interaction, amount: int):
    # safety check: only you can run it
    if interaction.user.id != PUT_OWNER_ID:
        await interaction.response.send_message("❌ You can't use this command.", ephemeral=True)
        return

    add_money(interaction.user.id, amount)
    bal = get_balance(interaction.user.id)
    await interaction.response.send_message(
        f"✅ {interaction.user.mention}, you received {amount} Cephcoins. New balance: **{bal}**"
    )


@bot.tree.command(name="balance", description="Check your Cephcoin balance")
async def balance(interaction: discord.Interaction):
    bal = get_balance(interaction.user.id)
    if bal == 0:
        await interaction.response.send_message(f"{interaction.user.mention}, yikes, you're broke :( get more Cephcoins with /daily :>")
    else:
        await interaction.response.send_message(f"{interaction.user.mention}, you have **{bal}** Cephcoins :D")

@bot.tree.command(name="daily", description="Claim your daily Cephcoins")
async def daily(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    today = str(datetime.date.today())

    #uh this is making sure the user exists in economy
    cursor.execute("SELECT balance, streak, last_daily FROM economy WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()

    if row is None:
        # if they aint real then they aint money
        cursor.execute("INSERT INTO economy (user_id, balance, streak, last_daily) VALUES (?, ?, ?, ?)",
                        (user_id, 0, 0, None))
        conn.commit()
        balance, streak, last_daily = 0, 0, None
    else:
        balance, streak, last_daily = row

    # Boy i sure do wonder if they already claimed today
    if last_daily == today:
       await interaction.response.send_message(f"{interaction.user.mention}, you already claimed your daily Cephcoins today. Come back tomorrow for more :>")
       return

    # streak checking
    yesterday = str(datetime.date.today() - datetime.timedelta(days=1))
    if last_daily == yesterday:
        streak += 1
    else:
        streak = 1
    
    #reward computin
    streak_capped = min(streak, 5)
    reward = 50 + (streak_capped - 1) * 25
    balance += reward

    cursor.execute("UPDATE economy SET balance = ?, streak = ?, last_daily = ? WHERE user_id = ?",
                    (balance, streak, today, user_id))
    conn.commit()

    await interaction.response.send_message(
        f"{interaction.user.mention}, you claimed **{reward}** Cephcoins! "
        f"(Streak: {streak})"
    )
    
from discord import app_commands

@bot.tree.command(name="allin", description="Bet your entire balance with choosable odds")
@app_commands.describe(multiplier="Your Multiplier (2-10)")
async def allin (interaction: discord.Interaction, multiplier: int):
    if multiplier < 2 or multiplier > 10:
        await interaction.response.send_message("Multiplier must be between 2 and 10.", ephemeral=True)
        return
    user_id = str(interaction.user.id)
    bal = get_balance(user_id)
    if bal <= 0:
        await interaction.response.send_message(f"{interaction.user.mention}, you have no Cephcoins to bet!", ephemeral=True)
        return
    import random
    if random.randint(1, multiplier) == 1:
        # win
        new_balance = bal * multiplier
        cursor.execute("UPDATE economy SET balance = ? WHERE user_id = ?", (new_balance, user_id))
        conn.commit()
        await interaction.response.send_message(
            f"{interaction.user.mention}, you won! Your balance is now **{new_balance}** Cephcoins!"
        )
    else:
        # lose :(
        new_balance = 0
        cursor.execute("UPDATE economy SET balance = ? WHERE user_id = ?", (new_balance, user_id))
        conn.commit()
        await interaction.response.send_message(
            f"{interaction.user.mention}, you lost it all, your new balance is **0** Cephcoins."
        )

import random

# blackjack helper functions
suits = ["♠", "♥", "♦", "♣"]
ranks = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]

def create_deck():
    return [(rank, suit) for rank in ranks for suit in suits]

def hand_value(hand):
    value = 0
    aces = 0
    for rank, _ in hand:
        if rank in ["J", "Q", "K"]:
            value += 10
        elif rank == "A":
            value += 11
            aces += 1
        else:
            value += int(rank)

    # adjust aces from 11 to 1 if needed
    while value > 21 and aces:
        value -= 10
        aces -= 1

    return value   # <-- moved out of the for loop

    
def format_hand(hand):
    return ", ".join([f"{rank}{suit}" for rank, suit in hand])

# track active BJ
games = {}

# slash command to start blackjack
@bot.tree.command(name="blackjack", description="Play a game of Blackjack")
async def blackjack (interaction: discord.Interaction, bet: int):
    user_id= str(interaction.user.id)
    bal =  get_balance(user_id)

    if bet <= 0:
        await interaction.response.send_message("Be must be positive!", ephemeral=True)
        return
    if bal < bet:
        await interaction.response.send_message("You don't have enough Cephcoins!", ephemeral=True)
        return
    
    # take bet asap
    cursor.execute("UPDATE economy SET balance = balance - ? WHERE user_id = ?", (bet, user_id))
    conn.commit()

    deck = create_deck()
    random.shuffle(deck)
    player = [deck.pop(), deck.pop()]
    dealer = [deck.pop(), deck.pop()]

    games[user_id] = {
        "deck": deck,
        "player": player,
        "dealer": dealer,
        "bet": bet,
        "active": True
    }

    await interaction.response.send_message(
        f"**Blackjack started!**\n"
        f"Your hand: {format_hand(player)} (Value: {hand_value(player)})\n"
        f"Dealer shows: {dealer[0][0]}{dealer[0][1]}\n"
        f"Use `!hit` to draw another card or `!stand` to hold."
    )

# prefix commands for hit/stand
@bot.command()
async def hit(ctx):
    user_id = str(ctx.author.id)
    if user_id not in games or not games[user_id]["active"]:
        await ctx.send("You don’t have an active blackjack game. Start with `/blackjack [bet]`.")
        return

    game = games[user_id]
    game["player"].append(game["deck"].pop())
    value = hand_value(game["player"])

    if value > 21:
        games[user_id]["active"] = False
        await ctx.send(
            f"You drew {game['player'][-1][0]}{game['player'][-1][1]}.\n"
            f"Your hand: {format_hand(game['player'])} (Value: {value})\n"
            f"Bust! You lose your bet of {game['bet']} Cephcoins."
        )
        del games[user_id]
    else:
        await ctx.send(
            f"You drew {game['player'][-1][0]}{game['player'][-1][1]}.\n"
            f"Your hand: {format_hand(game['player'])} (Value: {value})\n"
            f"Use `!hit` or `!stand`."
        )

@bot.command()
async def stand(ctx):
    user_id = str(ctx.author.id)
    if user_id not in games or not games[user_id]["active"]:
        await ctx.send("You don’t have an active blackjack game. Start with `/blackjack [bet]`.")
        return

    game = games[user_id]
    deck, player, dealer, bet = game["deck"], game["player"], game["dealer"], game["bet"]
    games[user_id]["active"] = False

    # Dealer auto-play
    while hand_value(dealer) < 17:
        dealer.append(deck.pop())

    player_val = hand_value(player)
    dealer_val = hand_value(dealer)

    result = ""
    if dealer_val > 21 or player_val > dealer_val:
        add_money(user_id, bet * 2)
        result = f"You win! You earn {bet*2} Cephcoins."
    elif dealer_val == player_val:
        add_money(user_id, bet)
        result = f"It's a tie! Your {bet} Cephcoins are returned."
    else:
        result = f"Dealer wins. You lose your {bet} Cephcoins."

    await ctx.send(
        f"Your hand: {format_hand(player)} (Value: {player_val})\n"
        f"Dealer's hand: {format_hand(dealer)} (Value: {dealer_val})\n"
        f"{result}"
    )
    del games[user_id]

@bot.tree.command(name="getajob", description="Do an odd job to earn some Cephcoins!")
async def getajob(interaction: discord.Interaction):
    user_id = str(interaction.user.id)

    now = datetime.datetime.utcnow()
    last_time = get_last_getajob(user_id)
    if last_time:
        last_time = datetime.datetime.fromisoformat(last_time)
        diff = now - last_time
        if diff.total_seconds() < 3600:  # 1 hour cooldown
            remaining = 3600 - diff.total_seconds()
            minutes, seconds = divmod(int(remaining), 60)
            await interaction.response.send_message(
                f"There are no jobs available right now, come back in {minutes}m {seconds}s!",
                ephemeral=True
            )
            return

    # Outcome chances
    outcomes = [
        (20, "You got a job!\nUnfortunately you were robbed on the way there, and lost {loss} Cephcoins.", "robbed"),
        (40, "You got a job as a Cashier.\nYou were paid 8 Cephcoins.", 8),
        (20, "You got a job as a Delivery Driver.\nYou were paid 15 Cephcoins.", 15),
        (10, "You got a job as a Health Insurance Agent.\nYou were paid 35 Cephcoins.", 35),
        (10, "You did crime.\nYou obtained 150 Cephcoins.", 150),
    ]

    roll = random.randint(1, 100)
    cumulative = 0
    result = None
    for chance, message, reward in outcomes:
        cumulative += chance
        if roll <= cumulative:
            result = (message, reward)
            break

    # Apply result
    if result[1] == "robbed":
        bal = get_balance(user_id)
        loss = min(bal, 150)
        cursor.execute("UPDATE economy SET balance = balance - ? WHERE user_id = ?", (loss, user_id))
        conn.commit()
        text = result[0].format(loss=loss)
    else:
        add_money(user_id, result[1])
        text = result[0]

    # Save cooldown
    set_last_getajob(user_id, now.isoformat())

    await interaction.response.send_message(text)

bot.run("PUT_DISCORD_TOKEN_HERE")
