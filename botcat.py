#!/usr/bin/env python3


import sys
import argparse
import asyncio
import traceback
import telepot.async as telepot_async
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor


class Reader:
    def __init__(self, loop, stream):
        self._loop = loop
        self._stream = stream
        self._executor = ThreadPoolExecutor()

    async def __aiter__(self):
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


async def send_message(bot, args, message):
    retries = args.retries
    while True:
        try:
            await bot.sendMessage(args.channel,
                                  message,
                                  parse_mode=args.parse_mode)
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
    reader = Reader(loop, sys.stdin)
    bot = telepot_async.Bot(args.token, loop=loop)

    # If we don't need line-by-line output, go the easy way
    if not args.split_newlines:
        await send_message(bot, args, await reader.read())
        return

    # Go the hard way
    async for line in reader:
        await send_message(bot, args, line)


def main():
    args = parse_command_line()

    with closing(asyncio.get_event_loop()) as loop:
        loop.run_until_complete(transfer_stdin(loop, args))


if __name__ == "__main__":
    main()
