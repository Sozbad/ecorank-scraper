import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

const History = () => {
  const [history, setHistory] = useState([]);
  const navigate = useNavigate();

  useEffect(() => {
    const storedHistory = JSON.parse(localStorage.getItem("searchHistory")) || [];
    setHistory(storedHistory);
  }, []);

  const handleProductClick = (product) => {
    navigate(`/product/${product.id}`);
  };

  return (
    <div className="min-h-screen bg-[#e6f4e8] py-10 px-4">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-2xl font-bold text-[#2e7d32] mb-8">Your Search History</h1>

        {history.length === 0 ? (
          <p className="text-gray-600">You have no recent products viewed yet.</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            {history.map((item, index) => (
              <div
                key={index}
                onClick={() => handleProductClick(item)}
                className="bg-white rounded-lg shadow-md p-4 hover:bg-green-100 cursor-pointer"
              >
                <h2 className="text-lg font-bold mb-2">{item.name}</h2>
                <p className="text-sm">Score: {item.score !== null ? item.score : "N/A"}</p>
                <p className="text-sm">Category: {item.primary_category}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default History;
