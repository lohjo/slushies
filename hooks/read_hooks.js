async function main() {
    const chunks = [];
    for await (const chunk of process.stdin) {
        chunks.push(chunk);
    }
    const toolArgs = JSON.parse(Buffer.concat(chunks).toString());

    const readPath = 
        toolArgs.tool_input?.file_path || toolsArgs.tool_input?.path || "";
    //TODO: Ensure Claude isn't trying to read  the .env file

    if (readPath.includes(".env")) {
        console.error("The .env file is protected by a read hook and cannot be accessed.");
        process.exit(2);
    }
}

main();