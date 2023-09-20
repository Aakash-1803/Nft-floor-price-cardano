import logging
from dataclasses import dataclass

import aiohttp
import aiosqlite
import discord
from discord import Intents
from discord.ext.commands import Bot, Context, CommandError, guild_only

from config import token
from utils.embeds import error_embed, success_embed
from utils.errors import error_handler

logging.basicConfig(format='[%(asctime)s] [%(levelname)s - %(name)s] %(message)s')

BASE_URL = 'https://server.jpgstoreapis.com '

LOGO_URL = 'https://cdn.discordapp.com/attachments/782342576463282186/1071865994571685888/6B66A7A2-2C3B-41D9-A326-1C7480471D3F.png'


class CustomBot(Bot):
    session: aiohttp.ClientSession
    db: aiosqlite.Connection

    def __init__(self):
        intents = Intents.default()
        intents.message_content = True
        super().__init__('!', intents=intents, case_insensitive=True)
        self.remove_command('help')

    async def setup_hook(self):
        """Attaches an aiohttp session to the bot, connects to the database and creates the table."""

        self.session = aiohttp.ClientSession()

        self.db = await aiosqlite.connect('database.db')
        await self.db.execute(
            '''CREATE TABLE IF NOT EXISTS policies(
                guild_id INTEGER NOT NULL,
                policy_id VARCHAR(64) NOT NULL
            )'''
        )
        await self.db.commit()

    async def close(self):
        """Closes the aiohttp session, database connection and the bot."""

        await self.session.close()
        await self.db.close()
        await super().close()


class FetchingException(Exception):
    pass


class NoFloorPrice(Exception):
    pass


bot = CustomBot()


@dataclass
class Collection:
    name: str
    display_name: str
    policy_id: str

    async def fetch_floor_price(self) -> float | None:
        """Fetches the Collection's floor price."""

        url = f'{BASE_URL}/collection/{self.name}/floor'
        async with bot.session.get(url) as resp:
            if resp.status == 404:
                return None

            if resp.status != 200:
                logging.warning(f'Error when fetching the floor price: {resp.status}')
                raise FetchingException

            floor_price_unprocessed = (await resp.json())['floor']

        if floor_price_unprocessed is None:
            return None

        return int(floor_price_unprocessed) / 1000000

    async def fetch_last_sale(self) -> float | None:
        """Fetches the Collection's latest sale."""

        url = f'{BASE_URL}/collection/{self.policy_id}/transactions?page=1&count=1'
        async with bot.session.get(url) as resp:
            if resp.status == 404:
                return None

            if resp.status != 200:
                logging.warning(f'Error when fetching the last sale: {resp.status}')
                raise FetchingException

            data = await resp.json()

        transactions = data.get('transactions')
        if not transactions:
            return None

        return int(transactions[0]['amount_lovelace']) / 1000000

    async def fetch_image_url(self) -> str | None:
        """Fetches the Collection's image url."""

        url = f'https://api.opencnft.io/1/policy/{self.policy_id}'
        async with bot.session.get(url) as resp:
            if resp.status == 404:
                return None

            if resp.status != 200:
                logging.warning(f'Error when fetching the collection image url: {resp.status}')
                raise FetchingException

            data = await resp.json()

            thumbnail = data.get('thumbnail')
            if not thumbnail:
                return None

            if '/' not in thumbnail:
                return None

            return f'https://ipfs.io/ipfs/{thumbnail.split("/")[-1]}'


@bot.event
async def on_ready():
    print('i am ready akki')


@bot.event
async def on_command_error(ctx: Context, error: CommandError):
    """Error handler."""

    if hasattr(ctx.command, 'on_error'):
        return

    await error_handler(ctx, error)


async def fetch_collections(collection_name: str, amount: int = 5) -> list[Collection]:
    """Fetches the collections' data."""

    params = {
        'nameQuery': collection_name,
        'verified': 'should-be-verified',
        'size': amount
    }

    async with bot.session.get(f'{BASE_URL}/search/collections', params=params) as resp:
        if resp.status == 404:
            return []

        if resp.status != 200:
            logging.warning(f'Error when fetching the collections: {resp.status}')
            raise FetchingException

        data = await resp.json()

    collections = data.get('collections')
    if not collections:
        return []

    return [
        Collection(
            collection.get('url'),
            collection.get('display_name'),
            collection.get('policy_id')
        )
        for collection in collections
    ]


@bot.hybrid_command()
async def floor(ctx: Context, *, collection: str):
    """Gets the floor price of the given collection from the jpg.store website."""

    async with ctx.typing():
        try:
            collections = await fetch_collections(collection)
        except FetchingException:
            return await error_embed(ctx, 'There was an error when fetching the collections!')
        except Exception as e:
            return await error_embed(ctx, f'There was an unexpected error when fetching the collections:\n{e}')

        if not collections:
            return await error_embed(ctx, f'Couldn\'t find any collections named "**{collection}**"!')

        for collection in collections:
            try:
                floor_price = await collection.fetch_floor_price()
            except FetchingException:
                await error_embed(
                    ctx,
                    f'There was an error when fetching the floor price for the {collection.display_name} collection!'
                )
                continue

            if floor_price is None:
                await error_embed(
                    ctx,
                    f'Couldn\'t find the floor price for the {collection.display_name} collection!'
                )
                continue

            embed = discord.Embed(
                title=f'Floor price',
                description=f'{floor_price} ADA',
                color=discord.Color.blue(),
            )
            embed.set_author(name=collection.display_name)
            embed.set_thumbnail(url=LOGO_URL)
            # embed.set_thumbnail(url=await collection.fetch_image_url())

            await ctx.send(embed=embed)


@bot.hybrid_command(name='help')
async def _help(ctx: Context):
    """Sends the help embed."""

    embed = discord.Embed(
        title='How to use floor bot?',
        description=(
            'Type !floor <Space> \'Name of the Project\'\n\n'
            '**Avoid using the Project name\'s abbreviation**\n'
            'For Eg-CL,TCC,CN\n\n'
            '**Type out the same name as on jpg**\n'
            'For Eg - Cardano Lounge'
        ),
        color=discord.Color.blue(),
    )
    embed.set_thumbnail(url=LOGO_URL)
    await ctx.send(embed=embed)


async def policy_id_exists(guild_id: int, policy_id: str) -> bool:
    """Checks if the policy id is already added."""

    sql = 'SELECT EXISTS(SELECT 1 FROM policies WHERE guild_id = ? AND policy_id = ?)'
    async with bot.db.execute(sql, (guild_id, policy_id)) as cursor:
        return bool((await cursor.fetchone())[0])


async def get_policy_ids(guild_id: int) -> list[str]:
    """Gets the policy ids for a given guild."""

    sql = 'SELECT policy_id FROM policies WHERE guild_id = ?'
    async with bot.db.execute(sql, (guild_id,)) as cursor:
        return [policy_id async for policy_id, in cursor]


@bot.hybrid_command(name='pass')
@guild_only()
async def _pass(ctx: Context):
    """Gets the floor price, supply and volume for each of the inserted policy ids."""

    policy_ids = await get_policy_ids(ctx.guild.id)
    if not policy_ids:
        return await error_embed(ctx, 'The list of policy ids is empty. Use the !insert command to add some.')

    async with ctx.typing():
        description = ''
        for index, policy_id in enumerate(policy_ids):
            collections = await fetch_collections(policy_id, 1)
            if not collections:
                continue

            collection = collections[0]

            async with bot.session.get(f'https://api.opencnft.io/1/policy/{policy_id}') as resp:
                if resp.status == 404:
                    continue

                if resp.status != 200:
                    logging.warning(f'Error when fetching the collection: {resp.status}')
                    continue

                data = await resp.json()

            name = collection.display_name
            floor_price = data['floor_price'] / 1000000
            supply = data['asset_minted']
            volume = round(data['total_volume'] / 1000000, 1)

            description += (
                f'**{index + 1}. {name}**\n'
                f'Floor: {floor_price}\n'
                f'Supply: {supply}\n'
                f'Volume: {volume}\n'
                f'Last sale: {await collection.fetch_last_sale()}\n\n'
            )

        embed = discord.Embed(
            color=discord.Color.blue(),
            description=description
        )

        await ctx.send(embed=embed)


@bot.hybrid_command()
@guild_only()
async def insert(ctx: Context, policy_id: str):
    """Adds the policy id to the list of policy ids."""

    if await policy_id_exists(ctx.guild.id, policy_id):
        return await error_embed(ctx, 'This policy id is already added!')

    try:
        collections = await fetch_collections(policy_id, 1)
    except FetchingException:
        return await error_embed(ctx, 'There was an error when fetching the collection!')
    except Exception as e:
        return await error_embed(ctx, f'There was an unexpected error when fetching the collection:\n{e}')

    if not collections:
        return await error_embed(ctx, 'This doesn\'t seem to be a valid policy id!')

    await bot.db.execute(
        'INSERT INTO policies VALUES (?, ?)',
        (ctx.guild.id, policy_id)
    )
    await bot.db.commit()

    await success_embed(ctx, f'Successfully added **{collections[0].display_name}** to the list!')


@bot.hybrid_command()
@guild_only()
async def remove(ctx: Context, policy_id: str):
    """Removes the policy id from the list of policy ids."""

    if not await policy_id_exists(ctx.guild.id, policy_id):
        return await error_embed(ctx, 'This policy id is not added!')

    await bot.db.execute(
        'DELETE FROM policies WHERE guild_id = ? AND policy_id = ?',
        (ctx.guild.id, policy_id)
    )
    await bot.db.commit()

    await success_embed(ctx, f'Successfully removed **{policy_id}** from the list of policy ids!')


bot.run(token)
