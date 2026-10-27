using System.Text;
using System.Text.Json;
using GetAndSee.Core.Device;
using GetAndSee.Core.Errors;

// Read-only on the phone. list walks /DCIM. pull writes one local file.
// This program never calls an AFC write, delete, rename, or mkdir.

Console.OutputEncoding = new UTF8Encoding(encoderShouldEmitUTF8Identifier: false);
Console.InputEncoding = new UTF8Encoding(encoderShouldEmitUTF8Identifier: false);

try
{
    if (args.Length == 1 && args[0] == "list")
    {
        await ListAsync();
        return 0;
    }

    if (args.Length == 3 && args[0] == "pull")
    {
        await PullAsync(args[1], args[2]);
        return 0;
    }
}
catch (DeviceException ex)
{
    Console.Error.WriteLine(ex.Message);
    return 1;
}
catch (Exception ex)
{
    Console.Error.WriteLine(ex.Message);
    return 1;
}

Console.Error.WriteLine("Usage: iphone-photos-host list");
Console.Error.WriteLine("       iphone-photos-host pull <remote-path> <local-path>");
return 2;

static async Task ListAsync()
{
    using var phone = new AfcIPhoneClient();
    await phone.ConnectAsync().ConfigureAwait(false);
    string name = phone.Device?.Name ?? "";
    if (string.IsNullOrWhiteSpace(name))
    {
        name = "iPhone";
    }

    Console.WriteLine(JsonSerializer.Serialize(new Dictionary<string, string>
    {
        ["phone"] = name,
    }));

    var enumerator = new DcimEnumerator(phone);
    await foreach (RemoteFile file in enumerator.EnumerateAsync().ConfigureAwait(false))
    {
        Console.WriteLine(JsonSerializer.Serialize(new Dictionary<string, object?>
        {
            ["path"] = file.Path,
            ["size"] = file.Size,
            ["mtime"] = file.ModifiedAt?.ToString("o"),
        }));
    }
}

static async Task PullAsync(string remotePath, string localPath)
{
    string full = Path.GetFullPath(localPath);
    string? parent = Path.GetDirectoryName(full);
    if (!string.IsNullOrEmpty(parent))
    {
        Directory.CreateDirectory(parent);
    }

    using var phone = new AfcIPhoneClient();
    await phone.ConnectAsync().ConfigureAwait(false);
    await using Stream source = await phone.OpenReadAsync(remotePath).ConfigureAwait(false);
    // CreateNew refuses to replace a file that is already on disk.
    await using var dest = new FileStream(full, FileMode.CreateNew, FileAccess.Write, FileShare.None);
    await source.CopyToAsync(dest).ConfigureAwait(false);
}
