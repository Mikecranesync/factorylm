import React, { useRef, useState } from 'react';

interface AudioPlayerProps {
  url: string;
}

const AudioPlayer: React.FC<AudioPlayerProps> = ({ url }) => {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);

  const playAudio = () => {
    if (audioRef.current) {
      audioRef.current.play();
      setIsPlaying(true);
    }
  };

  const pauseAudio = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      setIsPlaying(false);
    }
  };

  const stopAudio = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      setIsPlaying(false);
    }
  };

  return (
    <div>
      <audio ref={audioRef} src={url}>
      </audio>
      <button onClick={playAudio} disabled={isPlaying}>
        Play
      </button>
      <button onClick={pauseAudio} disabled={!isPlaying}>
        Pause
      </button>
      <button onClick={stopAudio} disabled={!isPlaying}>
        Stop
      </button>
    </div>
  );
};

export default AudioPlayer;
