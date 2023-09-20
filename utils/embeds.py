from discord import Embed, Color, Interaction, Member, User, TextChannel, Message, VoiceChannel
from discord.ext.commands import Context

__all__ = (
    'error_embed',
    'success_embed',
    'blue_embed'
)

ContextLike = Context | Interaction | TextChannel | Member | User | Message | VoiceChannel


async def error_embed(
        ctx: ContextLike,
        text: str,
        delete_after: int | None = 10,
        outside_text: str | None = None,
        **kwargs
) -> Message | None:
    """Sends an error embed."""

    embed = Embed(color=0xeb4034, description=f'❌ {text}')

    if isinstance(ctx, Interaction):
        if not ctx.response.is_done():
            return await ctx.response.send_message(embed=embed, ephemeral=True, **kwargs)
        else:
            return await ctx.followup.send(embed=embed, ephemeral=True, **kwargs)

    if isinstance(ctx, Message):
        return await ctx.reply(outside_text, embed=embed, delete_after=delete_after, **kwargs)

    return await ctx.send(outside_text, embed=embed, delete_after=delete_after, **kwargs)


async def success_embed(
        ctx: ContextLike,
        text: str,
        delete_after: int | None = 10,
        outside_text: str | None = None,
        **kwargs
) -> Message | None:
    """Sends a success embed."""

    embed = Embed(color=0x32a852, description=f'✅ {text}')

    if isinstance(ctx, Interaction):
        if not ctx.response.is_done():
            return await ctx.response.send_message(embed=embed, ephemeral=True, **kwargs)
        else:
            return await ctx.followup.send(embed=embed, ephemeral=True, **kwargs)

    if isinstance(ctx, Message):
        return await ctx.reply(outside_text, embed=embed, delete_after=delete_after, **kwargs)

    return await ctx.send(outside_text, embed=embed, delete_after=delete_after, **kwargs)


async def blue_embed(
        ctx: ContextLike,
        text: str,
        delete_after: int | None = None,
        outside_text: str | None = None,
        **kwargs
) -> Message | None:
    """Sends a blue embed."""

    embed = Embed(color=Color.blue(), description=text)

    if isinstance(ctx, Interaction):
        if not ctx.response.is_done():
            return await ctx.response.send_message(embed=embed, ephemeral=True, **kwargs)
        else:
            return await ctx.followup.send(embed=embed, ephemeral=True, **kwargs)

    if isinstance(ctx, Message):
        return await ctx.reply(outside_text, embed=embed, delete_after=delete_after, **kwargs)

    return await ctx.send(outside_text, embed=embed, delete_after=delete_after, **kwargs)
