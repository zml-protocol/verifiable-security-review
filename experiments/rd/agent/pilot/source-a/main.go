package rdpilot

type Request struct {
	Command string
}

func Execute(req Request) string {
	raw := req.Command
	command := raw
	return run(command)
}

func run(command string) string {
	return command
}
