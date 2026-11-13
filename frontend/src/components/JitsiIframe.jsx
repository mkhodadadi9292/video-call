// Isolated Jitsi embed: takes jitsiBaseUrl, roomName and jwt as props.
// The iframe loads Jitsi over HTTPS (camera/mic require a secure context).
export default function JitsiIframe({ jitsiBaseUrl, roomName, jwt }) {
  const src = `${jitsiBaseUrl}/${roomName}?jwt=${encodeURIComponent(jwt)}#config.prejoinPageEnabled=false&config.disableDeepLinking=true`

  return (
    <iframe
      data-testid="jitsi-iframe"
      src={src}
      allow="camera *; microphone *; display-capture *; fullscreen *; autoplay *"
      className="w-full h-full border-0"
      title="Meeting"
    />
  )
}
