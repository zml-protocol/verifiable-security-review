package rdpilot

import "strings"

type Request struct {
	Command string
}

func Execute(req Request) string {
	raw := req.Command
	command := strings.ReplaceAll(raw, ";", "")
	return run(command)
}

func run(command string) string {
	return command
}
