const http = require("http");

const port = Number(process.env.PORT || {{PORT}});
const server = http.createServer((_request, response) => {
  response.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
  response.end("<h1>{{SERVER_NAME}} is running</h1><p>Homebru Node.js server template.</p>");
});

server.listen(port, "0.0.0.0", () => {
  console.log(`{{SERVER_NAME}} listening on http://0.0.0.0:${port}`);
});
