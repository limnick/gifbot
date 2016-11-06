```
             ___  __              __
       __  /'___\/\ \            /\ \__
   __ /\_\/\ \__/\ \ \____    ___\ \ ,_\
 /'_ `\/\ \ \ ,__\\ \ '__`\  / __`\ \ \/
/\ \L\ \ \ \ \ \_/ \ \ \L\ \/\ \L\ \ \ \_
\ \____ \ \_\ \_\   \ \_,__/\ \____/\ \__\
 \/___L\ \/_/\/_/    \/___/  \/___/  \/__/
   /\____/     ___                 _      __
   \_/__/     / (_)___ ___  ____  (_)____/ /__
             / / / __ `__ \/ __ \/ / ___/ //_/
        BY  / / / / / / / / / / / / /__/ ,<
           /_/_/_/ /_/ /_/_/ /_/_/\___/_/|_|

    The latest in webscale technology
```

[example](https://sharktopus.com/sig.gif)

[larger example](https://sharktopus.com/site.gif)

## Setup
set up ZNC and create a user, and enable 40 lines of scrollback

put the user/pass/address in BOT_NAME/IRC_PASS/IRC_NETWORK

put the irc network you want displayed in the gif in PUB_IRC_NETWORK

put the channel in IRC_CHAN

`docker run -p 9000:9000 limnick/gifbot` with env vars set


## Kube
see `kube/` for example barebones kubernetes deployment

