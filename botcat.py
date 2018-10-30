#!/usr/bin/env python3


import argparse
import asyncio
import io
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing

import telepot.aio


def media_wrapper(func):
    async def wrapper(bot, chat_id, media, *args, **kwargs):
        with io.BytesIO(media) as stream:
            return await func(bot, chat_id, stream, *args, **kwargs)
    return wrapper


MESSAGE_TYPES = {
    "text": telepot.aio.Bot.sendMessage,
    "photo": media_wrapper(telepot.aio.Bot.sendPhoto),
    "audio": media_wrapper(telepot.aio.Bot.sendAudio),
    "document": media_wrapper(telepot.aio.Bot.sendDocument),
    "video": media_wrapper(telepot.aio.Bot.sendVideo),
    "voice": media_wrapper(telepot.aio.Bot.sendVoice)
}


class Reader:
    def __init__(self, loop, stream):
        self._loop = loop
        self._stream = stream
        self._executor = ThreadPoolExecutor()

    def __aiter__(self):
        return self

    async def __anext__(self):
        line = await self.readline()
        if line == "":
            raise StopAsyncIteration
        return line

    async def readline(self):
        return await self._loop.run_in_executor(self._executor,
                                                self._stream.readline)

    async def read(self):
        return await self._loop.run_in_executor(self._executor,
                                                self._stream.read)


def parse_command_line():
    def check_negative(argument):
        value = int(argument)
        if value < 0:
            raise argparse.ArgumentTypeError("'%s' is not a positive integer"
                                             % (argument,))
        return value

    parser = argparse.ArgumentParser(description="Redirects stdin to a "
                                                 "Telegram channel or chat.")
    parser.add_argument("token", help="API token of the Telegram bot.")
    parser.add_argument("channel", help="Chat ID or channel for broadcasts.")
    parser.add_argument("--type", help="Type of message to send. " +
                                       "(Defaults to %(default)s.)",
                        choices=MESSAGE_TYPES.keys(),
                        default="text")
    parser.add_argument("-m", "--parse-mode", help="How the input should be "
                                                   "parsed.",
                        choices=("HTML", "Markdown"))
    parser.add_argument("-s", "--split-newlines", help="If specified, each "
                                                       "input line will be "
                                                       "sent as an individual "
                                                       "message.",
                        action="store_true")
    parser.add_argument("-r", "--retries", help="How many times a failed send "
                                                "should be retried. Specify "
                                                "0 to retry indefinitely. "
                                                "(Defaults to %(default)s.)",
                        type=check_negative,
                        default="1")

    return parser.parse_args()


async def send_message(bot, args, message, **kwargs):
    retries = args.retries
    while True:
        try:
            await MESSAGE_TYPES[args.type](bot,
                                           args.channel,
                                           message,
                                           **kwargs)
        except:
            traceback.print_exc()

            # Continue if the original value was 0
            if args.retries == 0:
                continue

            # Abort if we tried as many times as we could
            retries -= 1
            if retries == 0:
                raise RuntimeError("Message %r was not sent after %d retries"
                                   % (message, args.retries))
        else:
            break


async def transfer_stdin(loop, args):
    bot = telepot.aio.Bot(args.token, loop=loop)

    # If we are not dealing with text, read everything from stdin as binary,
    # and send away.
    if args.type != "text":
        data = sys.stdin.buffer.read()
        await send_message(bot, args, data)
        return

    reader = Reader(loop, sys.stdin)

    # If we don't need line-by-line output, go the easy way
    if not args.split_newlines:
        await send_message(bot,
                           args,
                           await reader.read(),
                           parse_mode=args.parse_mode)
        return

    # Go the hard way
    async for line in reader:
        await send_message(bot, args, line, parse_mode=args.parse_mode)


def main():
    args = parse_command_line()

    with closing(asyncio.get_event_loop()) as loop:
        loop.run_until_complete(transfer_stdin(loop, args))


if __name__ == "__main__":
    main()
