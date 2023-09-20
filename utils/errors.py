from discord.ext import commands

from utils.embeds import *


async def error_handler(ctx: commands.Context, error: commands.CommandError):
    """Custom error handler."""

    if isinstance(error, commands.MissingRequiredArgument):
        return await error_embed(ctx, f'`{error.param.name}` is a required argument that is missing.')

    if isinstance(error, (commands.MissingPermissions, commands.CheckFailure)):
        return await error_embed(ctx, 'You don\'t have permission to use this command.')

    raise error
