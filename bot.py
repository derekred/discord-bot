import discord
import gspread
import json
import os
from google.oauth2.service_account import Credentials

scopes = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_json = json.loads(os.getenv("GOOGLE_CREDENTIALS"))
creds = Credentials.from_service_account_info(creds_json, scopes=scopes)
gc = gspread.authorize(creds)

SHEET_NAME = "Discord Members"
sheet = gc.open(SHEET_NAME).sheet1

if not sheet.get_all_values():
    sheet.append_row(["Discord Name", "Whop Username", "Joined At", "Invited By"])

intents = discord.Intents.default()
intents.members = True
intents.invites = True

client = discord.Client(intents=intents)

GENERAL_CHANNEL_ID = 1478844102379569356  # Replace with your general channel ID

pending_members = set()
invite_cache = {}

@client.event
async def on_ready():
    for guild in client.guilds:
        invites = await guild.fetch_invites()
        invite_cache[guild.id] = {inv.code: inv.uses for inv in invites}
    print(f'Bot is online as {client.user}')

@client.event
async def on_invite_create(invite):
    invite_cache[invite.guild.id][invite.code] = invite.uses

@client.event
async def on_member_join(member):
    if member.id in pending_members:
        return

    try:
        records = sheet.get_all_values()
        for row in records:
            if row and row[0] == str(member):
                print(f"{member} already in sheet, skipping DM")
                return

        pending_members.add(member.id)

        # Find who invited the member
        inviter = "Unknown"
        new_invites = await member.guild.fetch_invites()
        for inv in new_invites:
            cached_uses = invite_cache.get(member.guild.id, {}).get(inv.code, 0)
            if inv.uses > cached_uses:
                if inv.inviter:
                    inviter = str(inv.inviter)
                break
        invite_cache[member.guild.id] = {inv.code: inv.uses for inv in new_invites}

        # Mention in general channel
        general_channel = client.get_channel(GENERAL_CHANNEL_ID)
        if general_channel:
            await general_channel.send(
                f"👋 Welcome {member.mention}! "
                f"Please check your DMs and reply with your **Whop username** to get access."
            )

        # Send DM
        await member.send(
            f"Welcome to the server, {member.name}!\n"
            f"Please reply with your Whop username to get access. You have 5 minutes to respond."
        )

        def check(m):
            return m.author == member and isinstance(m.channel, discord.DMChannel)

        response = await client.wait_for("message", check=check, timeout=300.0)
        whop_username = response.content.strip()

        sheet.append_row([
            str(member),
            whop_username,
            str(member.joined_at),
            inviter
        ])

        await member.send(f"Got it! Your Whop username {whop_username} has been saved.")
        print(f"Saved: {member} -> {whop_username} | Invited by: {inviter}")

        if general_channel:
            await general_channel.send(f"✅ {member.mention} has been verified!")

    except discord.Forbidden:
        print(f"Could not DM {member.name}")
    except TimeoutError:
        await member.send("You did not respond in time. Please contact an admin.")
        general_channel = client.get_channel(GENERAL_CHANNEL_ID)
        if general_channel:
            await general_channel.send(f"⚠️ {member.mention} did not respond in time. Please contact an admin.")
    finally:
        pending_members.discard(member.id)

client.run(os.getenv("DISCORD_TOKEN"))
