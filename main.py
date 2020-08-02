import discord
from discord.ext import commands
from discord.utils import get
from discord import Guild
from discord import Embed
import creds

import random
import asyncio
import json

from pprint import pprint
import aioodbc


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
                   help_command=commands.DefaultHelpCommand(dm_help=True))

bot.messagesToCheck = []

@bot.event
async def on_ready():
    conn = await establish_connection()
    cur = await conn.cursor()
    bot.cur = cur

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
    await checkMessagesForConfirmation(bot.messagesToCheck)

### HERE BE MEMES ###
@bot.command(brief="Punish the bot")
async def bad(ctx):
    await ctx.send("I'm sorry, I'll try to do better 😢")

@bot.command(brief="Punish the bot")
async def Bad(ctx):
    await ctx.send("I'm sorry, I'll try to do better 😢")

@bot.command(brief="Praise the bot")
async def Good(ctx):
    await ctx.send("Thanks!")

@bot.command(brief="Praise the bot")
async def good(ctx):
    await ctx.send("Thanks!")

@bot.command(brief="Roast BlueAngelMan36")
async def blue(ctx):
    await ctx.send('Blueangelman36 is a B O O M E R')

@bot.command(brief="Roast BlueAngelMan36")
async def Blue(ctx):
    await ctx.send('Blueangelman36 is a B O O M E R')

@bot.command(brief="Roast Ben")
async def ben(ctx):
    await ctx.send('Ben smells like ass, ngl.')

@bot.command(brief="Roast Ben")
async def Ben(ctx):
    await ctx.send("Ben is a bot. I know, because I am also a bot.")
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
        Please repost with a photo attached to the message that contains the ?log invocation.
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

async def insertAmount(messageId, amount, resource, member, imageUrl, quantity):
    results = await bot.cur.execute("SELECT resourcebot.insert_payout(?,?,?,?,?,?)",
                                    amount, resource, member, imageUrl, messageId, quantity)
    await results.commit()
    rows = await results.fetchall()
    print(rows)
    try:
        payout_id = rows[0][0]
    except IndexError:
        print('More than one row/result returned')
    return payout_id

async def waitForConfirmation(ctx):
    returned = await bot.wait_for('reaction_add', check=checkForBot, timeout=None)
    print('Whoo!')
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
        cur = bot.cur
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
    await ctx.send(f"To check the resources you can log, use ?resources to see their names")

async def respondInvalidAmount(ctx):
    member = ctx.message.author.mention
    await ctx.send(f"Sorry {member}, the amount you listed is invalid. Please only enter integer values. I will delete your message shortly.")

async def insertMemberId(memberId, authorNickname):
    results = await bot.cur.execute("SELECT resourcebot.insert_member(?,?)", memberId, authorNickname)
    await results.commit()

async def checkMessagesForConfirmation(messagesToCheck):
    while True:
        for message in messagesToCheck:
            index = messagesToCheck.index(message)
            channel = message.channel
            newMsg = await channel.fetch_message(message.id)
            reactions = newMsg.reactions
            for reaction in reactions:
                async for user in reaction.users():
                    if user.bot:
                        pass
                    else:
                        for role in user.roles:
                            if ((role.id in bot.payoutRoles) or (role.id in bot.payerRoles)) and (reaction.emoji == '\U00002705'):
                                print("Confirmed!")
                                await removeMessageToMessageList(messagesToCheck, index)
                                await approvePayout(user.id, message.id)
                                #TODO error logging

                            elif ((role.id in bot.payoutRoles) or (role.id in bot.payerRoles)) and (reaction.emoji == '\U0000274E'):
                                print('Rejected!')
                                await removeMessageToMessageList(messagesToCheck, index)
                                await rejectPayout(user.id, message.id)
                                #TODO error logging

                            else:
                                continue
        await asyncio.sleep(1)

async def addMessageToMessageList(messagesToCheck, message):
    messagesToCheck.append(message)

async def removeMessageToMessageList(messagesToCheck, position):
    messagesToCheck.pop(position)

async def approvePayout(messageId, approverId):
    try:
        results = await bot.cur.execute('SELECT resourcebot.approve_payout(?,?)', approverId, messageId)
        await results.commit()
        return True
    except:
        return False

async def approveManually(payoutId, approverId):
    try:
        results = await bot.cur.execute('SELECT resourcebot.approve_payout(?,?)', approverId, messageId)
        await results.commit()
        return True
    except:
        return False

async def rejectPayout(messageId, approverId):
    try:
        results = await bot.cur.execute('SELECT resourcebot.reject_payout(?,?)', approverId, messageId)
        await results.commit()
        return True
    except:
        return False

async def calculateAmount(resource, amount):
    try:
        results = await bot.cur.execute('SELECT resourcebot.calculate_amount(?,?)', resource, amount)
        await results.commit()
        amount = await results.fetchall()
        return amount[0][0]
    except:
        return None

async def fetchBalance(memberId):
    try:
        results = await bot.cur.execute('SELECT resourcebot.calculate_amount(?,?)', resource, amount)
        await results.commit()
        amount = await results.fetchall()
        return amount[0][0]
    except:
        return None

########################


### Actual Commands ####

@bot.command(brief='Check payout balance',
             description='Retrieves the approved, pending, and rejected payout balances.')
async def balance(ctx, memberMention):
    memberId = memberMention.replace("@!","").replace("<","").replace(">","")
    print(f"memberId: {memberId}")
    results = await bot.cur.execute('SELECT resourcebot.balance(?)', memberId)
    await results.commit()
    result = await results.fetchall()
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
        await ctx.send(embed=embed)

    except TypeError:
        await ctx.send("This player currently doesn't have any payouts logged.")

@bot.command(brief='Check payout balance',
             description='Retrieves the approved, pending, and rejected payout balances.')
async def Balance(ctx, memberMention):
    await balance(ctx, memberMention)

@bot.command(brief='Check payout balance',
             description='Retrieves the approved, pending, and rejected payout balances.')
async def Balances(ctx, memberMention):
    await balance(ctx, memberMention)

@bot.command(brief='Check payout balance',
             description='Retrieves the approved, pending, and rejected payout balances.')
async def balances(ctx, memberMention):
    await balance(ctx, memberMention)

@bot.command(description="The main command for logging ingredients. MUST ATTACH A PHOTO TO THIS MESSAGE",
             brief= "Use this to log ingredients")
async def Log(ctx, quantity, resource):
    await log(ctx, quantity, resource)

@bot.command(description="The main command for logging ingredients. MUST ATTACH A PHOTO TO THIS MESSAGE",
             brief= "Use this to log ingredients")
async def log(ctx, quantity, resource):
    print("Content:", ctx.message.content)
    print("Attachments:",ctx.message.attachments)
    print("Quantity:", quantity)
    print("Resource:", resource)
    memberId = ctx.message.author.id
    authorNickname = ctx.message.author.display_name

    if len(ctx.message.attachments) == 0:
        await respondNoPhoto(ctx)
        await ctx.message.delete(delay=5)

    else:
        try:
            imageUrl = ctx.message.attachments[0].url
            messageId = ctx.message.id
            validateResource(resource)
            validateAmount(quantity)
            try:
                await insertMemberId(memberId, authorNickname)
                amount = await calculateAmount(resource, quantity)
                print(f"The amount is: {amount}")
                payoutId = await insertAmount(messageId, amount, resource, memberId, imageUrl, quantity)
                await notifyPayoutTeam(ctx, payoutId=payoutId)
                await addCheckMarkReaction(ctx.message)
                await addCrossMarkReaction(ctx.message)
                await addMessageToMessageList(bot.messagesToCheck, ctx.message)

            except InterruptedError:
                print("Resource and amount was valid, an error occurred inserting into DB.")

        except TypeError:
            await respondInvalidResource(ctx)
            await ctx.message.delete(delay=5)

        except ValueError:
            await respondInvalidAmount(ctx)
            await ctx.message.delete(delay=5)

    return None

@bot.command(description="Returns all the resources you can currently log and their per-unit payout price.",
             brief="See current resources & prices.")
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

    await ctx.send(embed=embed)

@bot.command(brief="See current resources & prices.")
async def prices(ctx):
    await resources(ctx)

@bot.command(description='''Use this to manually approve a payout BY payoutId in the event the bot dies. 
            The payoutId is in the confirmation message the bot sends when it's logged. No message, it's not
            logged.''',
             brief="Payout Team Only! Can use this to approve payouts manually if the reactions fail")
async def approve(ctx, payoutId):
    print(bot.payoutRoles)
    approver = ctx.message.author
    memberId = approver.id
    roles = approver.roles
    for role in roles:
        #print(role.id)
        if (role.id in bot.payoutRoles) or (role.id in bot.payerRoles):
            print('Valid approver!')
            results = await bot.cur.execute('SELECT resourcebot.approve_payout_manual(?,?)', payoutId, memberId)
            await results.commit()
            await ctx.send("Approved!")
            return
        else:
            continue

    return print(f'{approver.mention} is not a valid approver.')

@bot.command(description="Use this to log that you paid out a member for all their APPROVED payouts logged.",
             brief="R4+ Only! Used to log a payout occurred.")
async def payout(ctx, memberMention):
    message = ctx.message
    author = message.author
    payerId = author.id

    idNums = [s for s in memberMention if s.isdigit()]
    memberId = int(''.join(idNums))

    for role in author.roles:
        if role.id in bot.payerRoles:
            results = await bot.cur.execute('SELECT resourcebot.payout_member(?,?)', memberId, payerId)
            await results.commit()
            rows = await results.fetchall()
            total = rows[0][0]
            if total is not None:
                await ctx.send(f"Logged {'${:9,}'.format(total)} payout!")
            else:
                await ctx.send("This player did not have any approved payouts. MODS!")
            return
        else:
            continue
    await ctx.send(f"{author.mention} is not authorized to pay out members.")
    await ctx.message.delete(delay=15)

#########################


bot.run(creds.token)