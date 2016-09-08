#include "pick2d.h"
#include <unordered_map>

void geopick(const Eigen::MatrixXd& V,
	     std::vector<std::reference_wrapper<const Eigen::MatrixXi>> Fs,
             Eigen::MatrixXd &outV,
             Eigen::MatrixXi &outF)
{
	std::unordered_map<int, int> old2new;
	Eigen::VectorXi usingMarker;
	usingMarker.setZero(V.rows());
	for (auto Fref : Fs) {
		const Eigen::MatrixXi& F = Fref.get();
		for (int i = 0; i < F.rows(); i++)
			for (int j = 0; j < F.cols(); j++)
				usingMarker(F(i,j)) = 1;
	}
	outV.resize(usingMarker.sum(), V.cols());
	int iter = 0;
	for (int i = 0; i < V.rows(); i++) {
		if (usingMarker(i) == 0)
			continue;
		outV.row(iter) = V.row(i);
		old2new[i] = iter;
		iter++;
	}
	size_t nf = 0;
	for (auto F : Fs)
		nf += F.get().rows();
	outF.resize(nf, 3);
	iter = 0;
	for (auto Fref : Fs) {
		const Eigen::MatrixXi& F = Fref.get();
		for (int i = 0; i < F.rows(); i++) {
			for (int j = 0; j < outF.cols(); j++)
				outF(iter, j) = old2new[F(i, j)];
			iter++;
		}
	}
}
