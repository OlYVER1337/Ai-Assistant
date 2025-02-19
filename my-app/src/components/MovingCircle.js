import React, { useState, useEffect } from "react";
import { motion } from "framer-motion";

const MovingCircle = ({ response, isSpeaking, isLoading }) => {
  const [mouthShape, setMouthShape] = useState("-");
  const [position, setPosition] = useState({ x: 0, y: 0 });

  // Các variants
  const bubbleVariants = {
    initial: { opacity: 0, scale: 0.8 },
    animate: { opacity: 1, scale: 1 },
    exit: { opacity: 0, scale: 0.8 }
  };

  const circleVariants = {
    loading: {
      rotate: [-45, 45],
      transition: {
        repeat: Infinity,
        repeatType: "reverse",
        duration: 1.5
      }
    },
    normal: {
      rotate: 0,
      transition: {
        duration: 0.5
      }
    }
  };

  // Styles
  const containerStyle = {
    position: "fixed",
    width: "100vw",
    height: "100vh",
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    zIndex: 100,
    pointerEvents: "none"
  };

  const circleStyle = {
    width: 150,
    height: 150,
    borderRadius: "50%",
    backgroundColor: "#FFD700",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    flexDirection: "column",
    pointerEvents: "auto",
    cursor: "grab",
    position: "relative"
  };

  const eyeStyle = {
    width: 20,
    height: 20,
    borderRadius: "50%",
    backgroundColor: "black",
    margin: "0 5px"
  };

  const mouthStyle = {
    width: 50,
    height: 10,
    borderRadius: "10px",
    backgroundColor: "black",
    marginTop: 10
  };

  const questionMarkStyle = {
    position: "absolute",
    top: "-30px",
    right: "-30px",
    fontSize: "120px",
    fontWeight: "bold",
    color: "#000",
    zIndex: 102,
    transform: "rotate(45deg)",
    textShadow: "2px 2px 4px rgba(0,0,0,0.2)"
  };

  const bubbleStyle = {
    position: "absolute",
    top: "-150px", // Điều chỉnh lên cao hơn
    right: "-250px", // Điều chỉnh sang phải
    background: "white",
    padding: "15px 20px",
    borderRadius: "15px",
    boxShadow: "0 4px 6px rgba(0, 0, 0, 0.1)",
    fontSize: "16px",
    maxWidth: "300px",
    textAlign: "center",
    zIndex: 101, // Giảm z-index xuống
    transform: "rotate(0deg)" // Bỏ rotate để dễ đọc
  };

  // Effects
  useEffect(() => {
    let interval;
    if (isSpeaking) {
      interval = setInterval(() => {
        setMouthShape(prev => (prev === "o" ? "-" : "o"));
      }, 200);
    } else {
      setMouthShape("-");
    }
    return () => clearInterval(interval);
  }, [isSpeaking]);

  const handleDrag = (_, info) => {
    setPosition({ x: info.point.x, y: info.point.y });
  };

  return (
    <div style={containerStyle}>
      <motion.div
        className="circle"
        drag
        dragConstraints={{
          left: -window.innerWidth/2 + 75,
          right: window.innerWidth/2 - 75,
          top: -window.innerHeight/2 + 75,
          bottom: window.innerHeight/2 - 75
        }}
        onDrag={handleDrag}
        variants={circleVariants}
        animate={isLoading ? "loading" : "normal"}
        style={circleStyle}
      >
        {/* Phần nội dung chính của hình tròn */}
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
          {/* Eyes */}
          <div style={{ display: "flex" }}>
            <div style={eyeStyle}></div>
            <div style={eyeStyle}></div>
          </div>

          {/* Mouth */}
          <motion.div
            animate={{
              scaleY: mouthShape === "o" ? 2 : 1,
              scaleX: isSpeaking ? 1.5 : 1,
            }}
            transition={{ duration: 0.2 }}
            style={mouthStyle}
          ></motion.div>
        </div>

        {/* Phần dấu chấm hỏi và bubble chat */}
        {isLoading ? (
          <motion.div style={questionMarkStyle}>?</motion.div>
        ) : (
          response && (
            <motion.div
              variants={bubbleVariants}
              initial="initial"
              animate="animate"
              exit="exit"
              style={bubbleStyle}
            >
              {response}
            </motion.div>
          )
        )}
      </motion.div>
    </div>
  );
};

export default MovingCircle;
