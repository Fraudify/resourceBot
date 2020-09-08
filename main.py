import discord
from discord.ext import commands
from discord.utils import get
from discord import Guild
from discord import Embed
from discord.ext.commands.errors import MissingRequiredArgument, UserInputError, CommandInvokeError
import creds

import random
import asyncio
import json

from pprint import pprint
import aioodbc
from pyodbc import DataError


async def establish_connection():
    conn_str = (
        "DRIVER={PostgreSQL Unicode};"  # TODO Put these into environment variables
        "DATABASE=noble;"
        "SERVER=192.168.0.100;"
    )
    UID = creds.uid
    PWD = creds.pwd
    conn_str = conn_str + 'UID=' + UID + ';' + 'PWD=' + PWD + ';'
    conn = await aioodbc.connect(dsn=conn_str)
    return conn

description = '''A bot designed to record ingredients.
                 Use the $ or no prefix to issue a command below to the bot.
                 Some commands are role/rank-restricted.
                 Happy farming!'''

bot = commands.Bot(command_prefix=['$',''],
                   description=description,
                   help_command=commands.DefaultHelpCommand(dm_help=True),
                   case_insensitive=True)

@bot.event
async def on_ready():
    conn = await establish_connection()
    bot.conn = conn

    print('Logged in as')
    print(bot.user.name)
    print(bot.user.id)
    print('------')
    # Create payouts roles dynamically for use later
    print(bot.guilds)

    # Janky way of getting payoutRoleIds for a single server
    ## This should really be done based on the context of the command being invoked
    guilds = await bot.fetch_guilds().flatten()
    noble_guild = guilds[0]
    roles = await noble_guild.fetch_roles()
    payoutRoles = []
    for role in roles:
        if 'Payout' in role.name:
            payoutRoles.append(role.id)
        else:
            #print(role.name, role.id)
            continue
    bot.payoutRoles = payoutRoles

    # Janky way of setting payer roles
    payerRoles = [570480920487002122, #General
                  604144936480407553, #Retired General
                  570483707425718273, #Captain
                  604144737061961748, #Retired Captain
                  626968407954292738, #Lieutenant
                  649393731103096833 # Retired Lieutenant
                  ]
    bot.payerRoles = payerRoles
    bot.resources = await getResources()
    bot.help_command.case_insensitive = True
    await checkMessagesForConfirmation()

### HERE BE MEMES ###
@bot.command(brief="Punish the bot")
async def bad(ctx):
    await ctx.send("I'm sorry, I'll try to do better 😢")

@bot.command(brief="Praise the bot")
async def good(ctx):
    await ctx.send("Thanks!")

@bot.command(brief="Roast BlueAngelMan36")
async def blue(ctx):
    await ctx.send('Blueangelman36 is a B O O M E R')

@bot.command(brief="Roast Ben")
async def ben(ctx):
    await ctx.send('Ben smells like ass, ngl.')
#####################


### Functions to reference in actual commands ####
async def addCheckMarkReaction(message):
    await message.add_reaction('\U00002705')
    return None

async def addCrossMarkReaction(message):
    await message.add_reaction('\U0000274E')
    return None

async def respondNoPhoto(ctx):
    authMemb = ctx.message.author.mention
    await ctx.send(
        f'''\nSorry {authMemb}, but you submitted a log request with no photo.
        Please repost with a photo attached to the message that contains the {bot.command_prefix[0]}log invocation.
        You will need one photo per ingredient logged. I will delete your message shortly.''')

async def notifyPayoutTeam(ctx, payoutRoles = None, payoutId=None):
    if not payoutRoles:
        payoutRoles = bot.payoutRoles
    msg = ctx.message
    guild = msg.guild
    list_of_roles = []
    for role in payoutRoles:
        list_of_roles.append(guild.get_role(role))
    send_str = f"Thank you for submitting a resource log. Your payoutId is {payoutId}. "
    send_str = send_str + f"Please wait for {[role.mention for role in list_of_roles]} to review and approve it. "
    send_str = send_str + "You may check your balance at any time with `$balance @discordName`"
    send_str = send_str.replace("[","").replace("]","").replace("'","")
    await ctx.send(send_str)


def checkForBot(reactionEmoji, userReacting):
    pprint(userReacting)
    print(type(userReacting))
    if userReacting.bot == True:
        return False
    else:
        return True

async def insertAmount(messageId, amount, resource, member, imageUrl, quantity, channelId):
    cur = await bot.conn.cursor()
    results = await cur.execute("SELECT resourcebot.insert_payout(?,?,?,?,?,?,?)",
                                    amount, resource, member, imageUrl, messageId, quantity, channelId)
    await results.commit()
    rows = await results.fetchall()
    print(rows)
    try:
        payout_id = rows[0][0]
    except IndexError:
        print('More than one row/result returned')
    return payout_id

async def waitForConfirmation(ctx):
    '''DEPRECATED'''
    returned = await bot.wait_for('reaction_add', check=checkForBot, timeout=None)
    #print('Whoo!')
    print(returned)
    reaction = returned[0]
    if reaction.emoji == '\U00002705':
        #print("Confirmed!")
        pass
    elif reaction.emoji == '\U0000274E':
        #print('Not confirmed')
        pass
    else:
        pass
        #print("Ya dun goofed kid")
    approverId = returned[1].id



async def approveAmount(ctx):
    pass

async def getResources(cur=None):
    if cur is None:
        cur = await bot.conn.cursor()
    await cur.execute("SELECT * FROM resourcebot.resources")
    rows = await cur.fetchall()
    resource_dict = {}
    for row in rows:
        resource_dict[row[1]] = row[2]
    return resource_dict

def validateResource(resource):
    print(f"The resource is {resource}")
    resource_str = str(resource).strip()
    resource_fmt = resource_str.lower()
    if resource_fmt in list(bot.resources):
        return True

    else:
        print("wat")
        raise TypeError

def validateAmount(amount):
    try:
        int(amount)
        return True
    except ValueError:
        raise ValueError

async def respondInvalidResource(ctx):
    member = ctx.message.author.mention
    await ctx.send(f"Sorry {member}, the resource you indicated is invalid. Please try again. I will delete your message shortly.")
    await ctx.send(f"To check the resources you can log, use {bot.command_prefix[0]}resources to see their names")

async def respondInvalidAmount(ctx):
    member = ctx.message.author.mention
    await ctx.send(f"Sorry {member}, the amount you listed is invalid. Please only enter integer values. I will delete your message shortly.")

async def respondMissingArgument(ctx):
    member = ctx.message.author.mention
    await ctx.send(f"Sorry {member}, you did not enter a quantity or a resource. I need both to log. I will delete your message shortly.")

async def insertMemberId(memberId, authorNickname):
    cur = await bot.conn.cursor()
    results = await cur.execute("SELECT resourcebot.insert_member(?,?)", memberId, authorNickname)
    await results.commit()

async def checkMessagesForConfirmation():
    while True:
        cur = await bot.conn.cursor()
        sql = await cur.execute("SELECT * FROM resourcebot.payouts_to_approve")
        results = await sql.fetchall()
        if len(results) > 0:
            for row in results:
                print(row)
                message_id = row[0]
                channel_id = row[1]
                channel = bot.guilds[0].get_channel(channel_id) # TODO: Remove this in favor of something less hardcoded
                try:
                    newMsg = await channel.fetch_message(message_id)
                except discord.errors.NotFound: #TODO: This shouldn't be handled here.
                    print(f"Message {message_id} has been deleted in {channel}.")
                    print("Removing this log from the database.")
                    cur = await bot.conn.cursor()
                    trxn = await cur.execute(f'DELETE FROM resourcebot.payouts WHERE message_id = {message_id}')
                    trxn.commit()
                    continue
                reactions = newMsg.reactions
                for reaction in reactions:
                    async for user in reaction.users():
                        if user.bot:
                            pass
                        else:
                            for role in user.roles:
                                if ((role.id in bot.payoutRoles) or (role.id in bot.payerRoles)) and (reaction.emoji == '\U00002705'):
                                    print("Confirmed!")
                                    payoutId = await approvePayout(user.id, message_id)
                                    await user.send(f"You have approved payoutId {payoutId} for {newMsg.author.nick}")
                                    await newMsg.add_reaction('\U0001F197')
                                    break
                                    #removeMessageToMessageList(index)
                                    #TODO error logging

                                elif ((role.id in bot.payoutRoles) or (role.id in bot.payerRoles)) and (reaction.emoji == '\U0000274E'):
                                    print('Rejected!')
                                    await rejectPayout(user.id, message_id)
                                    break
                                    #removeMessageToMessageList(index)
                                    #TODO error logging

                                else:
                                    continue
                print(f"Checked for reactions on {message_id}, didn't find any...")
                await asyncio.sleep(1)
            else:
                print("No messages to check, sleeping...")
                await asyncio.sleep(1)

def addMessageToMessageList(message):
    bot.messagesToCheck.append(message)

def removeMessageToMessageList(position):
    bot.messagesToCheck.pop(position)

async def approvePayout(messageId, approverId):
    cur = await bot.conn.cursor()
    trnx = await cur.execute('SELECT resourcebot.approve_payout(?,?)', approverId, messageId)
    results = await trnx.fetchall()
    await trnx.commit()
    payoutId = results[0][0]
    return payoutId

async def approveManually(payoutId, approverId):
    try:
        cur = await bot.conn.cursor()
        results = await cur.execute('SELECT resourcebot.approve_payout_manual(?,?)', approverId, messageId)
        await results.commit()
        return True
    except:
        return False

async def rejectPayout(messageId, approverId):
    try:
        cur = await bot.conn.cursor()
        results = await cur.execute('SELECT resourcebot.reject_payout(?,?)', approverId, messageId)
        await results.commit()
        return True
    except:
        return False

async def calculateAmount(resource, amount):
    try:
        cur = await bot.conn.cursor()
        results = await cur.execute('SELECT resourcebot.calculate_amount(?,?)', resource, amount)
        await results.commit()
        amount = await results.fetchall()
        return amount[0][0]
    except:
        return None

async def fetchBalance(memberId):
    try:
        cur = await bot.conn.cursor()
        results = await cur.execute('SELECT resourcebot.calculate_amount(?,?)', resource, amount)
        await results.commit()
        amount = await results.fetchall()
        return amount[0][0]
    except:
        return None

########################


### Actual Commands ####

@bot.command(brief='Check payout balance',
             description='Retrieves the approved, pending, and rejected payout balances.',
             aliases=['balances'])
async def balance(ctx, memberMention):
    if '@' not in memberMention:
        await ctx.send(f"You did not @mention a player. Make sure to use @yourDiscordName. Like this: <@626554408389312532>!")
        return None
    author = ctx.message.author
    #print(f"This is the author of the message {author}. It is a type {type(author)}")
    memberId = memberMention.replace("@","").replace('!','').replace("<","").replace(">","")
    print(f"memberId: {memberId}")
    cur = await bot.conn.cursor()
    results = await cur.execute('SELECT resourcebot.balance(?)', memberId)
    result = await results.fetchall()
    print(result)
    try:
        result = result[0][0]
        result = json.loads(result)
        embed_dict = {
            'title': "Current Payout Balances",
            'description': 'Payout Amounts We Currently Have For the Selected Player'
        }
        embed = Embed.from_dict(embed_dict)
        for field in result.keys():
            field_fmt = field.replace("_"," ").title()
            value = result[field]

            if type(value) is int:
                value_fmt = '${:9,}'.format(value)
            else:
                value_fmt = value

            embed.add_field(name=field_fmt, value=value_fmt)
        await ctx.message.author.send(embed=embed)
        await ctx.message.delete(delay=5)

    except TypeError:
        await ctx.message.author.send("This player currently doesn't have any payouts logged.")
        await ctx.message.delete(delay=5)

@balance.error
async def balance_error(ctx, error):
    if isinstance(error, MissingRequiredArgument):
        await ctx.send(
            f"You did not @mention a player. Make sure to use @yourDiscordName. Like this: <@626554408389312532>!")
        return None
    else:
        print(f'Odd-ass error: {error}')


@bot.command(description="The main command for logging ingredients. MUST ATTACH A PHOTO TO THIS MESSAGE",
             brief= "Use this to log ingredients")
async def log(ctx, quantity, resource):
    #print("Content:", ctx.message.content)
    #print("Attachments:",ctx.message.attachments)
    #print("Quantity:", quantity)
    #print("Resource:", resource)
    memberId = ctx.message.author.id
    authorNickname = ctx.message.author.display_name

    if len(ctx.message.attachments) == 0:
        await respondNoPhoto(ctx)
        await ctx.message.delete(delay=5)

    else:
        try:
            imageUrl = ctx.message.attachments[0].url
            messageId = ctx.message.id
            channelId = ctx.message.channel.id
            validateResource(resource)
            validateAmount(quantity)
            try:
                await insertMemberId(memberId, authorNickname)
                amount = await calculateAmount(resource, quantity)
                print(f"The amount is: {amount}")
                payoutId = await insertAmount(messageId, amount, resource, memberId, imageUrl, quantity, channelId)
                await notifyPayoutTeam(ctx, payoutId=payoutId)
                await addCheckMarkReaction(ctx.message)
                await addCrossMarkReaction(ctx.message)

            except InterruptedError:
                print("Resource and amount was valid, an error occurred inserting into DB.")

        # except TypeError:
        #     await respondInvalidResource(ctx)
        #     await ctx.message.delete(delay=5)

        except ValueError:
            await respondInvalidAmount(ctx)
            await ctx.message.delete(delay=5)

    return None

@log.error
async def log_error(ctx, error):
    if isinstance(error, MissingRequiredArgument):
        await respondMissingArgument(ctx)
        await ctx.message.delete(delay=5)

@bot.command(description="Returns all the resources you can currently log and their per-unit payout price.",
             brief="See current resources & prices.",
             aliases=['prices', 'resource'])
async def resources(ctx):
    if bot.resources is None:
        bot.resources = await getResources()

    embed_dict = {
        'title':"Resource Prices",
        'description': 'Current configuration for prices'
    }
    embed = Embed.from_dict(embed_dict)
    for resource in bot.resources.keys():
        embed.add_field(name=resource.title(), value=bot.resources[resource])

    await ctx.message.author.send(embed=embed)
    await ctx.message.delete(delay=5)

# @bot.command(description='''Use this to manually approve a payout BY payoutId in the event the bot dies.
#             The payoutId is in the confirmation message the bot sends when it's logged. No message, it's not
#             logged.''',
#              brief="Payout Team Only! Can use this to approve payouts manually if the reactions fail")
# async def approve(ctx, payoutId):
#     #print(bot.payoutRoles)
#     approver = ctx.message.author
#     memberId = approver.id
#     roles = approver.roles
#     for role in roles:
#         #print(role.id)
#         if (role.id in bot.payoutRoles) or (role.id in bot.payerRoles):
#             print('Valid approver!')
#             cur = await bot.conn.cursor()
#             results = await cur.execute('SELECT resourcebot.approve_payout_manual(?,?)', payoutId, memberId)
#             await results.commit()
#             rows = await results.fetchall()
#             print(rows)
#             if rows[0][0]:
#                 await ctx.send(f"Approved payoutId {rows[0][0]}!")
#                 return
#             else:
#                 return await ctx.send(f"The payoutId specified, {payoutId}, was not found. Please check and try again.")
#         else:
#             continue
#     await ctx.send(f"<@{approver.id}> You are not able to approve payouts. Please contact a Payout team member.")
#     await ctx.message.delete(delay=15)
#     return
# @approve.error
# async def approve_error(ctx, error):
#     if isinstance(error, MissingRequiredArgument):
#         await ctx.send(f"You did not provide me a payoutId to approve. Try again with `{bot.command_prefix[0]}approve <payoutId>`")
#     elif isinstance(error.original, DataError):
#         await ctx.send(f"The payoutId you provided was invalid. Please check the number and try again.")

@bot.command(description="Use this to log that you paid out a member for all their APPROVED payouts logged.",
             brief="R4+ Only! Used to log a payout occurred.",
             aliases=['pay'])
async def payout(ctx, memberMention):
    message = ctx.message
    author = message.author
    payerId = author.id

    idNums = [s for s in memberMention if s.isdigit()]
    memberId = int(''.join(idNums))

    for role in author.roles:
        if role.id in bot.payerRoles:
            cur = await bot.conn.cursor()
            results = await cur.execute('SELECT resourcebot.payout_member(?,?)', memberId, payerId)
            await results.commit()
            rows = await results.fetchall()
            total = rows[0][0]
            if total is not None:
                await ctx.send(f"Logged {'${:9,}'.format(total)} payout for <@{memberId}>!")
            else:
                await ctx.send("This player did not have any approved payouts. MODS!")
            return
        else:
            continue
    await ctx.send(f"{author.mention} is not authorized to pay out members.")
    await ctx.message.delete(delay=15)
    return
@payout.error
async def payout_error(ctx, error):
    if isinstance(error.original, ValueError):
        await ctx.send(f"The memberId provided was not valid.")
    elif isinstance(error.original, DataError):
        print('Something weird happened while paying...')
    else:
        print(error.__dict__)

@bot.command()
async def names(ctx):
    nick_id = {}
    for guild in bot.guilds:
        for member in guild.members:
            nick_id[member.nick] = member.id
    print(nick_id)
    return

@bot.command()
async def needsApproval(ctx):
    msg_urls =[]
    for message in bot.messagesToCheck:
        msg_urls.append(message.jump_url)
    print(msg_urls)
    return None

@bot.command()
async def channelDetails(ctx):
    channel_id = ctx.message.channel.id
    print(channel_id)
#########################


bot.run(creds.token)